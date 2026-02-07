@REM Scan servers
uv run python src/rsshub_monitor/scan_servers.py --output temp/results/servers.json

@REM Scan namespace
uv run python src/rsshub_monitor/scan_namespace.py --rss-output temp/results/namespace.json --concurrent --valid-hours 0
