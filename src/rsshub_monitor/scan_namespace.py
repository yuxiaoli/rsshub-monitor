import argparse
import asyncio
import json
import os
import random
import sys
from urllib.parse import urljoin

import httpx
from tqdm import tqdm


async def load_domain_item(domain_item: str, client: httpx.AsyncClient) -> list[str]:
    """
    Try to load a domain item. If domain_item is a local file or a URL returning a JSON array,
    then filter for objects where "status" is true and return their "url" properties.
    Otherwise, treat domain_item as a plain domain string.
    """
    if os.path.exists(domain_item):
        try:
            with open(domain_item, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return [item["url"] for item in data if item.get("status") is True]
        except Exception:
            pass
        return [domain_item]
    else:
        try:
            r = await client.get(domain_item, timeout=10)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return [item["url"] for item in data if item.get("status") is True]
        except Exception:
            pass
        return [domain_item]


async def load_domains(domain_inputs: list[str]) -> list[str]:
    """
    Process a list of domain inputs. Each input can be a plain string
    or a JSON file path/URL. Returns a combined list of domain strings.
    """
    domains = []
    async with httpx.AsyncClient(timeout=10) as client:
        for d in domain_inputs:
            loaded = await load_domain_item(d, client)
            domains.extend(loaded)
    return domains


async def check_route(route, client, normalized_domains, verbose, timeout, semaphore):
    """
    Check if the route is online.
    
    - If 'example' is missing, return (route, False).
    - If 'example' is absolute, use it.
    - If relative, pick one random domain from normalized_domains to build the full URL.
    - After a 200 status, also check if the response is XML by examining the Content-Type header
      or if the response text starts with "<?xml".
    
    Returns a tuple (route, online) where online is True if the HTTP GET returns status 200
    and the content is XML.
    """
    async with semaphore:
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
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()
                # Check if the Content-Type contains "xml" or if the text starts with an XML declaration.
                if "xml" in content_type or response.text.lstrip().startswith("<?xml"):
                    online = True
                else:
                    online = False
            else:
                online = False
        except Exception:
            online = False

        result_str = "✅" if online else "❌"
        line = f"Testing URL: {full_url} ... {result_str}"
        if online or verbose:
            tqdm.write(line)
        return route, online


async def process_routes(data, client, normalized_domains, verbose, timeout, concurrency):
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []
    total_routes = sum(len(provider.get('routes', {})) for provider in data.values())
    pbar = tqdm(total=total_routes, desc="Checking routes")
    for provider in data.values():
        for route in provider.get('routes', {}).values():
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


async def main_async(source, output, rss_output, domain_inputs, verbose, timeout, concurrency):
    # Load domains from inputs.
    domain_list = await load_domains(domain_inputs)
    if not domain_list:
        domain_list = ["https://rsshub.app"]
    else:
        domain_list = [
            d if (d.startswith("http://") or d.startswith("https://")) else "https://" + d
            for d in domain_list
        ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RSSHubChecker/1.0; +https://github.com/DIYgod/RSSHub)"
    }
    async with httpx.AsyncClient(headers=headers) as client:
        # Load JSON data.
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

        data = await process_routes(data, client, domain_list, verbose, timeout, concurrency)

        # Count working example URLs.
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
                print(f"Updated JSON saved to {output}")
            except Exception as e:
                print(f"Error writing to output file: {e}")
                sys.exit(1)
        else:
            print("No output file specified; updated JSON not saved.")

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
        description="Check if a route is online based on its 'example' URL and create a JSON file for all online RSS endpoints."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="https://rsshub.app/api/namespace",
        help=("Path to a local JSON file or a URL to fetch the JSON from. "
              "Defaults to 'https://rsshub.app/api/namespace'.")
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to output file to save the updated JSON. If not provided, the updated JSON is not saved."
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
        default=["https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/servers.json"],
        help=("Either a plain domain string or a path/URL to a JSON file containing an array of server objects "
              "with schema: { 'url': <str>, 'location': <str>, 'maintainer': <str>, 'maintainerUrl': <str>, 'status': <bool> }. "
              "Only servers with 'status': true are used. Defaults to "
              "'https://raw.githubusercontent.com/yuxiaoli/rsshub-monitor/refs/heads/main/data/servers.json'.")
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
    # --concurrent accepts an optional number; if provided without a number, uses os.cpu_count(), default is 1.
    parser.add_argument(
        "--concurrent",
        nargs="?",
        const=os.cpu_count(),
        type=int,
        default=1,
        help="Number of concurrent requests to allow. If provided without a number, uses the number of CPU cores. Defaults to 1 if not provided."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(main_async(args.source, args.output, args.rss_output, args.domain, args.verbose, args.timeout, args.concurrent))


if __name__ == "__main__":
    main()
