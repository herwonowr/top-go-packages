#!/usr/bin/env bash

# Prevents script from running if there are any errors
set -e

# Generate and minify
python3 clickhouse.py
jq -c . < top-go-packages.json > top-go-packages.min.json
echo 'star_count,project' > top-go-packages.csv
jq -r '.rows[] | [.star_count, .project] | @csv' top-go-packages.json >> top-go-packages.csv
