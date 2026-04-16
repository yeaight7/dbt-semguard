# dbt-semguard

Catch semantic breaking changes in dbt metrics before they land in production.

`dbt-semguard` is a CLI-first semantic change detector for dbt Semantic Layer definitions. It compares two versions of the semantic contract, classifies changes as `breaking`, `risky`, or `safe`, and renders local or GitHub-friendly output without requiring warehouse access or dbt runtime internals.

## Install

```bash
python -m pip install .
```

## CLI

Extract a canonical contract from YAML or a manifest:

```bash
semguard extract --source yaml --project-dir examples/ecommerce_dbt_project --output base-contract.json
semguard extract --source manifest --manifest manifest.json --output manifest-contract.json
```

Compare two states:

```bash
semguard diff --base-ref main --head-ref HEAD --project-dir .
semguard diff --base-contract base-contract.json --head-contract head-contract.json --format markdown
semguard diff --base-manifest base-manifest.json --head-manifest head-manifest.json --format json
semguard check --base-ref main --head-ref HEAD --project-dir . --fail-on breaking
```

## Output

`diff` and `check` emit one of:

- `text`
- `markdown`
- `json`

JSON reports contain:

- `summary`
- `highest_severity`
- `blocking`
- `changes`
- `metadata`

## GitHub Action

Use the included composite action from this repository:

```yaml
jobs:
  semguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: ./
        with:
          base-ref: ${{ github.event.pull_request.base.sha }}
          head-ref: ${{ github.sha }}
          fail-on: breaking
```

The action writes:

- a Markdown summary to the workflow summary
- a JSON artifact named `semguard-report`
- a failing status when the configured threshold is reached

## Example project

An example latest-spec dbt project lives in [examples/ecommerce_dbt_project](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/examples/ecommerce_dbt_project).

## Documentation

- [Contract spec](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/docs/contract-spec.md)
- [Severity rules](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/docs/severity-rules.md)
- [Roadmap](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/docs/roadmap.md)
