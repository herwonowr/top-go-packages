# /// script
# requires-python = ">=3.10"
# ///
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


AWESOME_GO_URL = (
    "https://raw.githubusercontent.com/avelino/awesome-go/main/README.md"
)
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com"


def fetch_awesome_go_repos() -> list[str]:
    """Parse awesome-go README.md and extract unique GitHub repo names."""
    print("Fetching awesome-go README.md...")
    req = urllib.request.Request(
        AWESOME_GO_URL,
        headers={"User-Agent": "top-go-packages/1.0"},
    )
    with urllib.request.urlopen(req) as response:
        content = response.read().decode("utf-8")

    # Match github.com/{owner}/{repo} from markdown links
    pattern = re.compile(r"github\.com/([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)")
    matches = pattern.findall(content)

    # Deduplicate, lowercase, filter out non-package entries
    seen: set[str] = set()
    repos: list[str] = []
    skip_prefixes = (
        "avelino/awesome-go",
        "awesome-go/",
    )
    for match in matches:
        repo = match.lower().rstrip("/")
        if repo in seen:
            continue
        if any(repo.startswith(prefix) for prefix in skip_prefixes):
            continue
        seen.add(repo)
        repos.append(repo)

    print(f"Found {len(repos)} unique GitHub repos from awesome-go")
    return repos


def get_clickhouse_stars(repos: list[str]) -> str:
    """Query ClickHouse for GitHub star counts of awesome-go repos."""
    print(f"Querying ClickHouse for star counts of {len(repos)} repos...")

    params = {"user": "demo", "default_format": "JSON"}

    # Build repo list for SQL IN clause
    repo_list = ", ".join(f"'{r}'" for r in repos)
    query = f"""
        SELECT repo_name, stars
        FROM github.top_repos
        WHERE lower(repo_name) IN ({repo_list})
        ORDER BY stars DESC
        LIMIT 5000"""

    url = CLICKHOUSE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=query.encode("utf-8"), method="POST")
    with urllib.request.urlopen(req) as response:
        data = response.read().decode("utf-8")
    return data


def reformat_clickhouse_json(input_data: dict, repos_set: set[str]) -> None:
    """Reformat ClickHouse response to match top-pypi-packages structure."""
    rows = []
    for row in input_data["data"]:
        repo = row["repo_name"].lower()
        if repo not in repos_set:
            continue
        rows.append(
            {
                "star_count": int(row["stars"]),
                "project": f"github.com/{row['repo_name']}",
            }
        )

    # Sort by star count descending
    rows.sort(key=lambda r: r["star_count"], reverse=True)

    reformatted_data = {
        "last_update": dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "source": "ClickHouse (GitHub stars) + awesome-go",
        "metric": "star_count",
        "metric_description": (
            "GitHub star count. Go has no public download count API, "
            "so stars serve as the popularity proxy."
        ),
    }
    # Rename rows->total_rows and data->rows (matching top-pypi-packages)
    for k, v in input_data.items():
        if k == "rows":
            reformatted_data["total_rows"] = v
        elif k == "data":
            reformatted_data["rows"] = rows
        else:
            reformatted_data[k] = v

    Path("top-go-packages.json").write_text(
        json.dumps(reformatted_data, indent=0) + "\n"
    )
    print(f"Saved {len(rows)} packages to top-go-packages.json")


def main() -> None:
    repos = fetch_awesome_go_repos()
    repos_set = set(repos)
    data = get_clickhouse_stars(repos)
    data = json.loads(data)
    reformat_clickhouse_json(data, repos_set)


if __name__ == "__main__":
    main()
