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

## Coverage

`dbt-semguard` `v0.1.0` covers the highest-value semantic changes in the latest dbt Semantic Layer spec.

Covered extractors and inputs:

- Latest-spec YAML projects
- Explicit `manifest.json` input
- Canonical contract JSON emitted by `semguard extract`

Covered semantic comparisons:

- Semantic model add/remove and backing model changes
- Entity add/remove and entity type changes
- Dimension add/remove, type changes, and time granularity changes
- Simple metric aggregation, expression, label, and filter changes
- Ratio metric numerator and denominator changes
- Derived metric input metric changes
- Additive changes such as new entities, new dimensions, and new metrics

Current automated coverage:

- YAML extraction for the latest spec
- Manifest normalization
- Semantic diff severity mapping for breaking and risky changes
- CLI `extract`, `diff`, and `check`
- Checkout-free git ref mode

## Current Limitations

Known `v0.1.0` limitations are intentionally narrow:

- Manifest parsing expects an explicit artifact shape and does not yet attempt broad compatibility across real-world dbt manifest variants.
- The tool targets the latest Semantic Layer YAML spec only; legacy metric and semantic-model syntax is not included.
- Rename handling is intentionally conservative: a rename is treated as a removal plus an addition.
- File and line diagnostics are not emitted yet, even when the source could be traced.
- GitHub integration stops at workflow summary plus artifact upload; it does not manage PR comments or review threads.

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
- [Changelog](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/CHANGELOG.md)

## License

This project is open source under the MIT License. See [LICENSE](/C:/Users/Rivero/Documents/GitHub/dbt-semguard/LICENSE).
