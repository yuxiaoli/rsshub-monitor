# RSSHub Monitor

A Python tool for monitoring and managing RSSHub routes and servers. This project works with [RSSHub](https://github.com/DIYgod/RSSHub), an open source RSS feed aggregator that generates RSS feeds from various websites.

## Features

- Split RSSHub routes by categories
- Monitor RSSHub servers status
- Scan namespace for route availability
- Generate summary files for routes
- Compatible with [RSSHub's API](https://rsshub.app/api/reference)

## Related Resources

- [RSSHub Official Website](https://rsshub.app/)
- [RSSHub Documentation](https://docs.rsshub.app/)
- [RSSHub API Reference](https://rsshub.app/api/reference)
- [RSSHub Namespace API](https://rsshub.app/api/namespace)

## Installation

1. Make sure you have Python 3.11+ installed
2. Install using Poetry:

```bash
poetry install
```

## Usage

### 1. Monitor RSSHub Servers

Check the status of RSSHub public instances:

```bash
python src/rsshub_monitor/scan_servers.py [options]
```

Options:
- `path`: Path or URL to the Vue component containing the instances (defaults to RSSHub's official instance list)
- `--output`: Path to output JSON file with server status results

The script will:
- Parse the list of public RSSHub instances
- Check each server's availability using ping and HTTP requests
- Display status with ✅ or ❌ indicators
- Save results to JSON if output path is specified

### 2. Scan Namespace

Check the availability of RSSHub routes using the namespace API:

```bash
python src/rsshub_monitor/scan_namespace.py [options]
```

Options:
- `--source`: Source file path or URL (defaults to RSSHub namespace API)
- `--output`: Output file path
- `--domain`: RSSHub instance domain
- `--timeout`: Request timeout in seconds
- `--concurrent`: Maximum concurrent requests
- `--verbose`: Enable verbose output
- `--cache`: Enable caching of XML files (default directory: data/cache)
- `--category-cache`: Enable category-based caching of XML files (default directory: data/cache/categories)
- `--category-limit`: Maximum number of entries in category cache files (default: 100)

Examples:
```bash
# Basic scan
python src/rsshub_monitor/scan_namespace.py

# Enable XML caching
python src/rsshub_monitor/scan_namespace.py --cache

# Enable category-based caching with custom limit
python src/rsshub_monitor/scan_namespace.py --category-cache --category-limit 50

# Use both caching methods with custom directories
python src/rsshub_monitor/scan_namespace.py --cache custom/cache --category-cache custom/categories
```

### 3. Split Routes by Category

Split RSSHub routes into separate category files:

```bash
python src/rsshub_monitor/split_by_category.py [input_file] [options]
```

Options:
- `--output-dir`, `-o`: Output directory for category files (default: data/categories)
- `--create-summary`, `-s`: Create summary files with specified maximum items (default when flag present: 100)

Examples:
```bash
# Split routes using default settings
python src/rsshub_monitor/split_by_category.py

# Create summary files with default 100 items limit
python src/rsshub_monitor/split_by_category.py -s

# Create summary files with custom items limit
python src/rsshub_monitor/split_by_category.py -s 50
```

## Project Structure

```
rsshub-monitor/
├── data/               # Data files
│   ├── categories/     # Category-specific route files
│   ├── categories.json # List of all categories
│   └── servers.json    # RSSHub server instances
├── src/                # Source code
└── tests/              # Test files
```

## Dependencies

- httpx: HTTP client library
- tqdm: Progress bar library

## License

[MIT License](LICENSE)
