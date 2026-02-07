import json
import argparse
import httpx
import concurrent.futures
from tqdm import tqdm
from pathlib import Path

def check_url(url: str, timeout: int = 10) -> tuple[str, bool, str]:
    """Check if the RSS URL is working. Returns (url, is_working, content_or_error_msg)"""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            if response.status_code == 200:
                content = response.text
                # A basic check to see if it looks like an XML/RSS feed or JSON feed
                if "<rss" in content or "<feed" in content or "<?xml" in content or content.strip().startswith("{") or content.strip().startswith("["):
                    return url, True, content
                else:
                    return url, False, f"Status 200 but unexpected content start: {content[:50]}"
            else:
                return url, False, f"HTTP {response.status_code}"
    except Exception as e:
        return url, False, str(e)

def main():
    parser = argparse.ArgumentParser(description="Scan RSS URLs to filter out working ones.")
    parser.add_argument("--input", default=r"c:\workspace\python\rsshub-monitor\temp\results\rss.json", help="Path to input JSON file")
    parser.add_argument("--output", default=r"c:\workspace\python\rsshub-monitor\temp\results\working_rss.json", help="Path to output JSON file")
    parser.add_argument("--print-content", action="store_true", help="Print the content of working URLs")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found at {input_path}")
        return
        
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    rss_urls = data.get("rss_urls", [])
    if not rss_urls:
        print("No 'rss_urls' found in the input file.")
        return
        
    print(f"Loaded {len(rss_urls)} URLs. Starting scan...")
    
    working_urls = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(check_url, url): url for url in rss_urls}
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(rss_urls), desc="Scanning"):
            url, is_working, content = future.result()
            
            if is_working:
                working_urls.append(url)
                if args.print_content:
                    # Print without breaking the tqdm progress bar
                    tqdm.write(f"\n--- Content for {url} ---")
                    tqdm.write(content[:1000] + ("...\n[TRUNCATED]" if len(content) > 1000 else "\n"))
                    
    print(f"\nScan complete. Found {len(working_urls)} working URLs out of {len(rss_urls)}.")
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the working URLs
    data["rss_urls"] = working_urls
    if "metadata" in data:
        data["metadata"]["working_count"] = len(working_urls)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Working URLs saved to {output_path}")

if __name__ == "__main__":
    main()
