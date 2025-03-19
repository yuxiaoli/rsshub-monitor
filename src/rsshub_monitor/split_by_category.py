import json
import argparse
from pathlib import Path
from collections import defaultdict

def get_route_summary(route):
    """Extract key information from a route"""
    route_info = route['route']
    summary = {
        'provider_id': route['provider_id'],
        'provider_name': route['provider_name'],
        'route_key': route['route_key'],
        'route': {
            'name': route_info['name'],
            'path': route_info['path'],
            'example': route_info['example'],
            'parameters': route_info.get('parameters', {}),
            'description': route_info.get('description', '')
        }
    }
    return summary

def split_by_category(input_file: str, output_dir: str, create_summary: int = 0):
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Read input JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Group routes by category
    category_routes = defaultdict(list)
    for route in data:
        if 'route' in route and 'categories' in route['route']:
            # Create a simplified route by removing unwanted fields
            simplified_route = route.copy()
            route_info = simplified_route['route'].copy()
            fields_to_remove = ['features', 'radar', 'categories', 'maintainers', 
                              'location', 'lastChecked', 'online']
            for field in fields_to_remove:
                if field in route_info:
                    del route_info[field]
            simplified_route['route'] = route_info
            
            for category in route['route']['categories']:
                category_routes[category].append(simplified_route)
    
    # Write separate files for each category
    for category, routes in category_routes.items():
        output_file = output_path / f"{category}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(routes, f, ensure_ascii=False, indent=2)
        print(f"Created {output_file} with {len(routes)} routes")
    
    # Write categories list file in data directory
    categories_list = sorted(category_routes.keys())
    with open('data/categories.json', 'w', encoding='utf-8') as f:
        json.dump(categories_list, f, ensure_ascii=False, indent=2)
    
    # Create summary files if requested
    if create_summary:
        summary_dir = output_path / "summary"
        summary_dir.mkdir(exist_ok=True)
        
        for category, routes in category_routes.items():
            summary_file = summary_dir / f"{category}.json"
            routes_to_summarize = routes[:create_summary] if len(routes) > create_summary else routes
            summary_routes = [get_route_summary(route) for route in routes_to_summarize]
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_routes, f, ensure_ascii=False, indent=2)
            print(f"Created summary {summary_file} with {len(summary_routes)} routes (limited to {create_summary})")

def main():
    parser = argparse.ArgumentParser(description='Split RSSHub routes by category')
    parser.add_argument('input_file',
                      nargs='?',
                      default='data/online.json',
                      help='Input JSON file path (default: data/online.json)')
    parser.add_argument('--output-dir', '-o',
                      default='data/categories',
                      help='Output directory for category files (default: data/categories)')
    parser.add_argument('--create-summary', '-s',
                      nargs='?',
                      const=100,
                      type=int,
                      default=0,
                      help='Create summary files with specified maximum number of items (default when flag present: 100)')
    
    args = parser.parse_args()
    
    split_by_category(args.input_file, args.output_dir, args.create_summary)

if __name__ == '__main__':
    main()