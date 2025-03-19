import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import httpx
from tqdm import tqdm

DEFAULT_DOMAIN_SOURCE = "https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/servers.json"
DEFAULT_NAMESPACE_SOURCE = "https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/namespace.json"

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

async def check_route(route, client, normalized_domains, verbose, timeout, semaphore):
    """
    Check if the route is online.

    - If 'example' is missing, return (route, False).
    - If 'example' is absolute, use it.
    - If relative, pick one random domain from normalized_domains to build the full URL.
    - Verify that the response has status 200 and is valid XML.
    
    Updates route["lastChecked"] to current UTC time.
    Returns a tuple (route, online) where online is True if the check passes.
    """
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
            # Check status code first.
            if response.status_code != 200:
                online = False
            else:
                # Attempt to parse response content as XML.
                try:
                    ET.fromstring(response.text)
                    online = True
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

async def process_routes(data, client, normalized_domains, verbose, timeout, concurrency, valid_hours):
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []
    total_routes = sum(len(provider.get('routes', {})) for provider in data.values())
    pbar = tqdm(total=total_routes, desc="Checking routes")
    now = datetime.now(timezone.utc)
    for provider in data.values():
        for route in provider.get('routes', {}).values():
            # Skip re-checking if route is already online and lastChecked is recent.
            if route.get("online") and route.get("lastChecked"):
                try:
                    last_checked = parse_iso8601(route["lastChecked"])
                    diff = (now - last_checked).total_seconds() / 3600.0
                    if diff < valid_hours:
                        pbar.update(1)
                        continue
                except Exception:
                    pass
            task = asyncio.create_task(
                check_route(route, client, normalized_domains, verbose, timeout, semaphore)
            )
            tasks.append(task)
    for completed in asyncio.as_completed(tasks):
        route, is_online = await completed
        route["online"] = is_online
        pbar.update(1)
    pbar.close()
    return data

async def main_async(source, output, rss_output, domain_inputs, verbose, timeout, concurrency, valid_hours):
    domain_pool = await load_domain_pool(domain_inputs)
    normalized_domains = [
        d if (d.startswith("http://") or d.startswith("https://")) else "https://" + d
        for d in domain_pool
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RSSHubChecker/1.0; +https://github.com/DIYgod/RSSHub)"
    }
    async with httpx.AsyncClient(headers=headers) as client:
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

        data = await process_routes(data, client, normalized_domains, verbose, timeout, concurrency, valid_hours)

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
        default="online_rss_endpoints.json",
        help="Path to output file to save the online RSS endpoints JSON. Defaults to 'online_rss_endpoints.json'."
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
    return parser.parse_args()

def main():
    args = parse_args()
    asyncio.run(main_async(args.source, args.output, args.rss_output, args.domain, args.verbose, args.timeout, args.concurrent, args.valid_hours))

if __name__ == "__main__":
    main()
