# Top Go Packages

A weekly dump of the top Go packages by GitHub stars:

* https://raw.githubusercontent.com/herwonowr/top-go-packages/main/top-go-packages.min.json

Unminified:

* https://raw.githubusercontent.com/herwonowr/top-go-packages/main/top-go-packages.json

## Why stars?

Go has no public download count API. Unlike PyPI and npm, the Go module proxy
does not expose download statistics. GitHub stars serve as the best available
popularity proxy.

Packages are sourced from [awesome-go](https://github.com/avelino/awesome-go)
and ranked by star count via [ClickHouse](https://sql-clickhouse.clickhouse.com)
GitHub data.

## How it works

A [GitHub Actions workflow](.github/workflows/update.yml) runs every Monday.
It queries ClickHouse for star counts of all repos listed in awesome-go,
generates JSON/CSV, and commits the results back to this repo.

You can also trigger it manually via `workflow_dispatch`.

## Thanks

Thanks to [awesome-go](https://github.com/avelino/awesome-go) and
[ClickHouse](https://sql-clickhouse.clickhouse.com).
