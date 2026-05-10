# /// script
# requires-python = ">=3.10"
# ///
from __future__ import annotations

import base64
import concurrent.futures
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

AWESOME_GO_URL = "https://raw.githubusercontent.com/avelino/awesome-go/main/README.md"
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com"
GITHUB_API = "https://api.github.com/repos/{repo}/contents/go.mod"
MAX_WORKERS = 20


def _github_headers() -> dict[str, str]:
    """Build GitHub API headers, using GITHUB_TOKEN if available."""
    headers = {
        "User-Agent": "top-go-packages/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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

    # Deduplicate and lowercase
    seen: set[str] = set()
    repos: list[str] = []
    for match in matches:
        repo = match.lower().rstrip("/")
        if repo in seen:
            continue
        seen.add(repo)
        repos.append(repo)

    print(f"Found {len(repos)} unique GitHub repos from awesome-go")
    return repos


def fetch_go_module_path(repo: str) -> str | None:
    """Fetch go.mod via GitHub API and return the module path, or None."""
    url = GITHUB_API.format(repo=repo)
    req = urllib.request.Request(url, headers=_github_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = base64.b64decode(data["content"]).decode("utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("module "):
                return line.split(None, 1)[1]
    except Exception:
        pass
    return None


def resolve_module_paths(repos: list[str]) -> dict[str, str]:
    """Resolve Go module paths for all repos concurrently.

    Returns a dict mapping lowercase repo name to its Go module path.
    Repos without a valid go.mod are excluded.
    """
    print(f"Resolving Go module paths for {len(repos)} repos...")
    repo_to_module: dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_repo = {
            executor.submit(fetch_go_module_path, repo): repo for repo in repos
        }
        done = 0
        for future in concurrent.futures.as_completed(future_to_repo):
            repo = future_to_repo[future]
            done += 1
            if done % 100 == 0:
                print(f"  resolved {done}/{len(repos)}...")
            module_path = future.result()
            if module_path:
                repo_to_module[repo] = module_path

    print(
        f"Resolved {len(repo_to_module)} Go modules "
        f"(skipped {len(repos) - len(repo_to_module)} non-Go repos)"
    )
    return repo_to_module


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


def reformat_clickhouse_json(
    input_data: dict,
    repo_to_module: dict[str, str],
) -> None:
    """Reformat ClickHouse response using resolved Go module paths."""
    rows = []
    for row in input_data["data"]:
        repo = row["repo_name"].lower()
        module_path = repo_to_module.get(repo)
        if not module_path:
            continue
        rows.append(
            {
                "star_count": int(row["stars"]),
                "project": module_path,
            }
        )

    # Sort by star count descending
    rows.sort(key=lambda r: r["star_count"], reverse=True)

    reformatted_data = {
        "last_update": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ClickHouse (GitHub stars) + awesome-go",
        "metric": "star_count",
        "metric_description": (
            "GitHub star count. Go has no public download count API, "
            "so stars serve as the popularity proxy."
        ),
    }
    # Rename rows->total_rows and data->rows
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
    repo_to_module = resolve_module_paths(repos)
    data = get_clickhouse_stars(list(repo_to_module.keys()))
    data = json.loads(data)
    reformat_clickhouse_json(data, repo_to_module)


if __name__ == "__main__":
    main()
