#!/usr/bin/env python3
import re
import json
import argparse
import httpx
import subprocess
import platform
from urllib.parse import urlparse

def fetch_content(path):
    """Fetch content from a URL or read from a local file."""
    if path.startswith("http://") or path.startswith("https://"):
        try:
            response = httpx.get(path)
            response.raise_for_status()
            return response.text
        except httpx.RequestError as e:
            print(f"Error fetching URL: {e}")
            return None
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return None

def parse_instances(content):
    """
    Extracts and parses the public instances from the provided Vue code.
    It locates the JavaScript array defined as "const instances = [...]"
    and converts it to valid JSON.
    """
    match = re.search(r'const\s+instances\s*=\s*(\[[\s\S]*?\])', content)
    if not match:
        print("Could not find the instances array in the content.")
        return None

    array_str = match.group(1)

    # Convert JavaScript object notation to valid JSON:
    # 1. Replace single quotes with double quotes.
    json_str = array_str.replace("'", '"')
    # 2. Quote object keys that are unquoted by matching keys preceded by '{' or ','.
    json_str = re.sub(r'([{,]\s*)(\w+)\s*:', r'\1"\2":', json_str)
    # 3. Remove trailing commas before closing braces or brackets.
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    try:
        instances = json.loads(json_str)
    except Exception as e:
        print("Error parsing JSON:", e)
        return None

    return instances

def check_instance(url):
    """
    Checks the server by:
    1. Pinging the host.
    2. Sending an HTTP GET request to {url}/test/hi.
    Returns a tuple (ping_success, http_success).
    """
    # Extract the host from the URL.
    parsed = urlparse(url)
    host = parsed.netloc

    # Ping the host.
    try:
        count_flag = "-n" if platform.system().lower() == "windows" else "-c"
        ping_cmd = ["ping", count_flag, "1", host]
        ping_result = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ping_success = (ping_result.returncode == 0)
    except Exception as e:
        print(f"Error executing ping for {host}: {e}")
        ping_success = False

    # Send HTTP GET request to {url}/test/hi using httpx.
    test_url = url.rstrip("/") + "/test/hi"
    try:
        response = httpx.get(test_url, timeout=5)
        http_success = response.is_success
    except httpx.RequestError as e:
        print(f"Error requesting {test_url}: {e}")
        http_success = False

    return ping_success, http_success

def main():
    parser = argparse.ArgumentParser(
        description="Parse public RSSHub instances from a Vue component file, check each server with a ping and HTTP GET to {url}/test/hi, and optionally write output JSON."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="https://raw.githubusercontent.com/RSSNext/rsshub-docs/refs/heads/main/.vitepress/theme/components/InstanceList.vue",
        help="Path or URL to the Vue component containing the instances."
    )
    parser.add_argument(
        "--output",
        help="Path to output JSON file (conforming to the provided schema).",
        default=None
    )
    args = parser.parse_args()

    content = fetch_content(args.path)
    if content is None:
        print("Failed to fetch or read content.")
        return

    instances = parse_instances(content)
    if instances is None:
        print("Failed to parse instances.")
        return

    results = []
    print("Parsed RSSHub Instances and Server Checks:")
    for instance in instances:
        url = instance.get("url")
        print(f"Instance: {url}")
        print(f"  Location: {instance.get('location')}")
        print(f"  Maintainer: {instance.get('maintainer')}")
        print(f"  Maintainer URL: {instance.get('maintainerUrl')}")
        
        ping_status, http_status = check_instance(url)
        overall_status = ping_status and http_status

        ping_symbol = "✅" if ping_status else "❌"
        http_symbol = "✅" if http_status else "❌"
        
        print(f"  Ping: {'Success' if ping_status else 'Failed'} {ping_symbol}")
        print(f"  GET {url.rstrip('/') + '/test/hi'}: {'Success' if http_status else 'Failed'} {http_symbol}\n")

        # Build result entry matching the JSON schema.
        result = {
            "url": instance.get("url"),
            "location": instance.get("location"),
            "maintainer": instance.get("maintainer"),
            "maintainerUrl": instance.get("maintainerUrl"),
            "status": overall_status
        }
        results.append(result)

    # If an output file path is provided, write the results with ensure_ascii=False.
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results written to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}")

if __name__ == "__main__":
    main()
