import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import httpx
from tqdm import tqdm

DEFAULT_DOMAIN_SOURCE = "https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/servers.json"
DEFAULT_NAMESPACE_SOURCE = "https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/namespace.json"
DEFAULT_CACHE_DIR = "data/cache"
DEFAULT_CATEGORY_CACHE_DIR = "data/cache/categories/"
DEFAULT_CATEGORY_CACHE_LIMIT = 100

def parse_iso8601(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

async def load_domains_from_url(url: str) -> list:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Error loading domains from URL {url}: {e}")
            return []
    return [item["url"] for item in data if item.get("online") is True and "url" in item]

def load_domains_from_file(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading domains from file {path}: {e}")
        return []
    return [item["url"] for item in data if item.get("online") is True and "url" in item]

async def load_domain_pool(domain_inputs: list) -> list:
    pool = []
    if not domain_inputs:
        domain_inputs = [DEFAULT_DOMAIN_SOURCE]
    for entry in domain_inputs:
        if os.path.exists(entry):
            loaded = load_domains_from_file(entry)
            if loaded:
                pool.extend(loaded)
            else:
                pool.append(entry)
        elif entry.startswith("http://") or entry.startswith("https://"):
            if entry.lower().endswith(".json"):
                loaded = await load_domains_from_url(entry)
                if loaded:
                    pool.extend(loaded)
                else:
                    pool.append(entry)
            else:
                pool.append(entry)
        else:
            pool.append(entry)
    return pool

# Add this function near the top with other utility functions
def get_cache_path(route_path: str, cache_dir: str) -> Path:
    """Generate consistent cache path for a route"""
    if route_path.startswith('http://') or route_path.startswith('https://'):
        route_path = route_path.split('/', 3)[-1] if len(route_path.split('/', 3)) > 3 else route_path
    url_hash = hashlib.md5(route_path.encode()).hexdigest()
    return Path(cache_dir) / f"{url_hash}.xml"

async def check_route(route, client, normalized_domains, verbose, timeout, semaphore, cache_dir=None, category_cache=None):
    async with semaphore:
        now = datetime.now(timezone.utc)
        example_url = route.get('example')
        if not example_url:
            if verbose:
                tqdm.write("No 'example' URL provided, marking as offline ❌")
            return route, False

        if not (example_url.startswith("http://") or example_url.startswith("https://")):
            chosen_domain = random.choice(normalized_domains)
            full_url = urljoin(chosen_domain, example_url)
        else:
            full_url = example_url

        try:
            response = await client.get(full_url, timeout=timeout)
            if response.status_code != 200:
                online = False
            else:
                try:
                    xml_content = response.text
                    ET.fromstring(xml_content)
                    online = True
                    # Save to regular cache if enabled
                    if cache_dir and online:
                        route_path = route.get('example', '')
                        cache_path = get_cache_path(route_path, cache_dir)
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_text(xml_content, encoding='utf-8')
                        if verbose:
                            tqdm.write(f"Cached XML to {cache_path}")

                    # Save to category cache if enabled
                    if category_cache and online and 'categories' in route:
                        for category in route['categories']:
                            category_path = Path(category_cache['dir']) / f"{category}.xml"
                            category_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Read existing entries
                            entries = []
                            if category_path.exists():
                                try:
                                    root = ET.parse(str(category_path)).getroot()
                                    entries = list(root.findall('.//item'))
                                except ET.ParseError:
                                    entries = []
                            
                            # Add new entry with route information
                            new_root = ET.fromstring(xml_content)
                            new_items = new_root.findall('.//item')
                            
                            # Add route metadata to each item
                            for item in new_items:
                                route_info = ET.SubElement(item, 'route')
                                ET.SubElement(route_info, 'provider_id').text = route.get('provider_id', '')
                                ET.SubElement(route_info, 'provider_name').text = route.get('provider_name', '')
                                ET.SubElement(route_info, 'route_path').text = route.get('path', '')
                                ET.SubElement(route_info, 'route_name').text = route.get('name', '')
                            
                            if new_items:
                                entries.extend(new_items)
                            
                            # Rotate if needed
                            if len(entries) > category_cache['limit']:
                                entries = entries[-category_cache['limit']:]
                            
                            # Create new XML document with category information
                            root = ET.Element('rss')
                            root.set('version', '2.0')
                            channel = ET.SubElement(root, 'channel')
                            ET.SubElement(channel, 'title').text = f"RSSHub - {category}"
                            ET.SubElement(channel, 'description').text = f"RSS feeds for {category} category"
                            
                            for entry in entries:
                                channel.append(entry)
                            
                            # Save file with proper XML formatting
                            tree = ET.ElementTree(root)
                            tree.write(str(category_path), encoding='utf-8', xml_declaration=True)
                            if verbose:
                                tqdm.write(f"Updated category cache: {category_path}")
                except Exception:
                    online = False
        except Exception:
            online = False

        # Update lastChecked to current UTC time.
        route["lastChecked"] = now.isoformat()
        result_str = "✅" if online else "❌"
        line = f"Testing URL: {full_url} ... {result_str}"
        if online or verbose:
            tqdm.write(line)
        return route, online

async def process_routes(data, client, normalized_domains, verbose, timeout, concurrency, valid_hours, cache_dir=None, category_cache=None):
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []
    total_routes = sum(len(provider.get('routes', {})) for provider in data.values())
    pbar = tqdm(total=total_routes, desc="Checking routes")
    now = datetime.now(timezone.utc)
    for provider_id, provider in data.items():
        for route_key, route in provider.get('routes', {}).items():
            # Add provider info to route for caching
            route['provider_id'] = provider_id
            route['provider_name'] = provider.get('name', '')
            route['route_key'] = route_key

            # Check if route is valid and cache exists
            if route.get("online") and route.get("lastChecked"):
                try:
                    last_checked = parse_iso8601(route["lastChecked"])
                    diff = (now - last_checked).total_seconds() / 3600.0
                    if diff < valid_hours:
                        # Check if cache exists
                        cache_exists = True
                        if cache_dir:
                            route_path = route.get('example', '')
                            cache_path = get_cache_path(route_path, cache_dir)
                            if not cache_path.exists():
                                cache_exists = False
                        
                        if category_cache and 'categories' in route:
                            for category in route['categories']:
                                category_path = Path(category_cache['dir']) / f"{category}.xml"
                                if not category_path.exists():
                                    cache_exists = False
                                    break
                        
                        if cache_exists:
                            pbar.update(1)
                            continue
                        
                        # Create cache if needed
                        task = asyncio.create_task(
                            check_route(route, client, normalized_domains, verbose, timeout, semaphore, cache_dir, category_cache)
                        )
                        tasks.append(task)
                        continue
                except Exception:
                    pass
            
            task = asyncio.create_task(
                check_route(route, client, normalized_domains, verbose, timeout, semaphore, cache_dir, category_cache)
            )
            tasks.append(task)
    for completed in asyncio.as_completed(tasks):
        route, is_online = await completed
        route["online"] = is_online
        pbar.update(1)
    pbar.close()
    return data

async def main_async(source, output, rss_output, domain_inputs, verbose, timeout, concurrency, valid_hours, cache_dir, category_cache=None):
    domain_pool = await load_domain_pool(domain_inputs)
    normalized_domains = [
        d if (d.startswith("http://") or d.startswith("https://")) else "https://" + d
        for d in domain_pool
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RSSHubChecker/1.0; +https://github.com/DIYgod/RSSHub)"
    }
    async with httpx.AsyncClient(headers=headers) as client:
        # print(source)
        if source.startswith("http://") or source.startswith("https://"):
            try:
                response = await client.get(source, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                print(f"Error fetching JSON from URL: {e}")
                sys.exit(1)
        else:
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error reading JSON file: {e}")
                sys.exit(1)

        # print(data)
        data = await process_routes(data, client, normalized_domains, verbose, timeout, concurrency, valid_hours, cache_dir, category_cache)

        working_count = sum(
            1 for provider in data.values() 
            for route in provider.get("routes", {}).values() 
            if route.get("online")
        )
        print(f"Total number of working example URLs: {working_count}")

        if output:
            try:
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"Updated namespace JSON saved to {output}")
            except Exception as e:
                print(f"Error writing to output file: {e}")
                sys.exit(1)
        else:
            print("No output file specified; updated namespace JSON not saved.")

        online_endpoints = []
        for provider_id, provider in data.items():
            provider_name = provider.get("name", "")
            for route_key, route in provider.get("routes", {}).items():
                if route.get("online"):
                    online_endpoints.append({
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "route_key": route_key,
                        "route": route
                    })
        try:
            with open(rss_output, 'w', encoding='utf-8') as f:
                json.dump(online_endpoints, f, indent=2, ensure_ascii=False)
            print(f"Online RSS endpoints saved to {rss_output}")
        except Exception as e:
            print(f"Error writing RSS endpoints to file: {e}")
            sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Check if routes (from a namespace JSON) are online based on their 'example' URL. "
                    "Routes that are already online and have been checked within a given number of hours are skipped."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/namespace.json",
        help=("Path to a local JSON file or a URL to fetch the namespace JSON from. "
              "Defaults to 'https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/namespace.json'.")
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to output file to save the updated namespace JSON. If not provided, the updated JSON is not saved."
    )
    parser.add_argument(
        "--rss-output",
        type=str,
        default="data/online.json",
        help="Path to output file to save the online RSS endpoints JSON. Defaults to 'data/online.json'."
    )
    parser.add_argument(
        "-d", "--domain",
        action="append",
        default=[],
        help=("Either a raw domain string or a path/URL to a JSON file (per the servers schema). "
              "If not provided, defaults to the default servers JSON.")
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity. Use -v, -vv, or -vvv for more output."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5,
        help="Timeout for HTTP requests in seconds. Defaults to 5."
    )
    parser.add_argument(
        "--concurrent",
        nargs="?",
        const=os.cpu_count(),
        type=int,
        default=1,
        help="Number of concurrent requests to allow. If provided without a number, uses the number of CPU cores. Defaults to 1 if not provided."
    )
    parser.add_argument(
        "--valid-hours",
        type=float,
        default=24,
        help="Number of hours before lastChecked that is considered valid. Routes that are online and were checked within this many hours are skipped. Defaults to 24."
    )
    parser.add_argument(
        "--cache",
        nargs="?",
        const=DEFAULT_CACHE_DIR,
        help=f"Enable caching of XML files. Optionally specify cache directory (default: {DEFAULT_CACHE_DIR})"
    )
    
    parser.add_argument(
        "--category-cache",
        nargs="?",
        const=DEFAULT_CATEGORY_CACHE_DIR,
        help=f"Enable category-based caching of XML files (default dir: {DEFAULT_CATEGORY_CACHE_DIR})"
    )
    
    parser.add_argument(
        "--category-limit",
        type=int,
        default=DEFAULT_CATEGORY_CACHE_LIMIT,
        help=f"Maximum number of entries in category cache files (default: {DEFAULT_CATEGORY_CACHE_LIMIT})"
    )
    
    return parser.parse_args()

def main():
    args = parse_args()
    category_cache = None
    if args.category_cache:
        category_cache = {
            'dir': args.category_cache,
            'limit': args.category_limit
        }
    
    asyncio.run(main_async(
        args.source, 
        args.output, 
        args.rss_output, 
        args.domain, 
        args.verbose, 
        args.timeout, 
        args.concurrent, 
        args.valid_hours,
        args.cache,
        category_cache
    ))

if __name__ == "__main__":
    main()
