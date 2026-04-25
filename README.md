# dbt-semguard

Catch semantic breaking changes in dbt metrics before they land in production.

`dbt-semguard` is a CLI-first semantic change detector for dbt Semantic Layer definitions. It compares two versions of the semantic contract, classifies changes as `breaking`, `risky`, or `safe`, and renders local or GitHub-friendly output without requiring warehouse access or dbt runtime internals.

## What Is This For?

`dbt-semguard` is a semantic PR guard for dbt metrics and semantic models.

It answers one question:

> What changed in the meaning of this metric?

That matters because many dbt changes are valid from a parser or build point of view, but still dangerous for downstream consumers.

For example, a PR may:

- change `gross_revenue` from `sum(order_total)` to `avg(order_total)`
- remove a dimension people use to slice a KPI
- change a ratio metric denominator
- widen or narrow a metric filter
- change entity or time-grain semantics

In all of those cases, dbt may still parse successfully and CI may still be green. But the business meaning of the metric has changed, and dashboards, notebooks, reverse ETL jobs, or APIs may silently start returning different answers.

`dbt-semguard` exists to catch that class of change before it reaches production.

## What It Does Exactly

`dbt-semguard` does not lint YAML style and it does not validate warehouse execution.

Instead, it:

1. reads the dbt Semantic Layer definition from two inputs
2. extracts only the semantic parts that affect meaning
3. builds a canonical contract for each side
4. diffs those contracts
5. classifies each change as `breaking`, `risky`, or `safe`
6. renders the result for local CLI use or GitHub Actions

In practical terms, it helps teams review semantic changes the same way they already review code changes.

## How It Works

The tool reduces dbt semantic definitions into a normalized contract that is easier to compare than raw YAML.

It keeps fields that affect meaning, such as:

- semantic model identity
- backing model name
- entities and entity types
- dimensions and time granularity
- metric type
- aggregation and expression
- filters
- ratio numerator and denominator

It intentionally ignores noise such as:

- descriptions
- docs blocks
- YAML ordering
- whitespace and comments

That means the output is focused on semantic drift, not formatting drift.

[//]: # (## How To Explain It To A Data Team)

[//]: # (Short version:)

[//]: # (> `dbt-semguard` tells you whether a PR changes the meaning of a metric, not just its code.)

[//]: # (Slightly longer version:)

[//]: # (> It compares the dbt Semantic Layer before and after a PR, strips away cosmetic YAML changes, and highlights only the changes that can affect how downstream users interpret or query a KPI.)

## Install

```bash
python -m pip install .
```

## How To Use It

### Run locally before opening a PR

Use this when you want to sanity-check semantic changes while you are still developing:

```bash
semguard diff --base-ref main --head-ref HEAD --project-dir .
semguard check --base-ref main --head-ref HEAD --project-dir . --fail-on breaking
```

Typical use:

- `diff` when you want to inspect what changed
- `check` when you want a blocking exit code for automation or local scripts

For monorepos, always point `--project-dir` at the dbt project root you want to analyze:

```bash
semguard diff --base-ref main --head-ref HEAD --project-dir analytics/dbt
```

Git ref mode and local YAML mode now both scope discovery to this directory.

### Compare exported contracts directly

Use this when you want to compare two precomputed semantic contracts:

```bash
semguard diff --base-contract base-contract.json --head-contract head-contract.json --format markdown
```

### Compare manifests explicitly

Use this when your workflow already has dbt `semantic_manifest.json` artifacts available:

```bash
semguard diff --base-manifest base-semantic-manifest.json --head-manifest head-semantic-manifest.json --format json
```

### Extract a contract

Use this when you want a stable machine-readable snapshot of semantic meaning:

```bash
semguard extract --source yaml --project-dir examples/ecommerce_dbt_project --output base-contract.json
semguard extract --source manifest --manifest semantic_manifest.json --output manifest-contract.json
```

### Configure YAML discovery with `.semguard.yml`

Create `.semguard.yml` in your dbt project root to control which YAML files are scanned:

```yaml
include:
  - models/**/*.yml
  - models/**/*.yaml
  - metrics/**/*.yml
  - metrics/**/*.yaml
  - semantic_models/**/*.yml
  - semantic_models/**/*.yaml
exclude:
  - target/**
  - dbt_packages/**
  - .venv/**
  - .github/**
```
If the file is not present, these defaults are applied automatically.


## Example Review Flow

1. A developer changes a metric or semantic model in dbt.
2. `dbt-semguard diff` compares the base branch and the current branch.
3. The tool reports semantic changes only.
4. The team decides whether the change is acceptable, needs migration planning, or should be blocked.
5. In CI, `semguard check --fail-on breaking` can fail the PR automatically.

## How To Read The Result

- `breaking`: the semantic meaning changed in a way that should usually block by default
- `risky`: the change may be legitimate, but downstream consumers should review it
- `safe`: cosmetic-only changes that do not appear in the semantic diff

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

`dbt-semguard` currently covers the highest-value semantic changes in the latest dbt Semantic Layer spec.

Covered extractors and inputs:

- Latest-spec YAML projects
- Explicit dbt `semantic_manifest.json` input
- Canonical contract JSON emitted by `semguard extract`

Covered semantic comparisons:

- Semantic model add/remove and backing model changes
- Semantic model default aggregation time dimension changes
- Entity add/remove, type changes, and expression changes
- Dimension add/remove, type changes, expression changes, and time granularity changes
- Simple metric aggregation, expression, label, filter, ownership, aggregation-time, and non-additive changes
- Ratio metric numerator and denominator changes
- Derived metric expression and input metric changes
- Cumulative metric input, window, grain-to-date, and period-aggregation changes
- Conversion metric entity, calculation, base metric, conversion metric, and constant-property changes
- Additive changes such as new entities, new dimensions, and new metrics

Current automated coverage:

- YAML extraction for the latest spec
- Manifest normalization
- Semantic diff severity mapping for breaking and risky changes
- Declarative field-coverage policy so contract fields are explicitly diffed, nested, or intentionally excluded
- Source diagnostics in extracted YAML contracts and change reports
- CLI `extract`, `diff`, and `check`
- Sticky PR comment delivery through the GitHub Action
- Checkout-free git ref mode
- CI smoke coverage for the published action path in both git-ref and manifest modes, including spaced manifest paths

## Current Limitations

Known `v0.4.0` limitations are intentionally narrow:

- Manifest parsing expects dbt `semantic_manifest.json`, not the general-purpose dbt `manifest.json` artifact.
- The tool targets the latest Semantic Layer YAML spec only; legacy metric and semantic-model syntax is not included.
- Rename handling is intentionally conservative: a rename is treated as a removal plus an addition.
- Source diagnostics are best-effort and currently strongest for YAML extraction; manifest-derived contracts may still lack file/line detail.
- GitHub integration supports sticky PR comments for pull_request workflows, but does not yet manage review-thread lifecycles or inline annotations.

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

      - uses: yeaight7/dbt-semguard@v0.4.0
        with:
          base-ref: ${{ github.event.pull_request.base.sha }}
          head-ref: ${{ github.sha }}
          fail-on: breaking
          pr-comment: true
          github-token: ${{ github.token }}
```

The action writes:

- a Markdown summary to the workflow summary
- a JSON artifact named `semguard-report`
- an optional sticky PR comment when `pr-comment: true`
- a failing status when the configured threshold is reached

This is the recommended setup when you want the semantic review to happen automatically on every PR.

## Migration notes (`v0.4.0`)

- Git ref extraction now scopes strictly to `--project-dir` for monorepos.
- YAML discovery now uses safe default include/exclude patterns.
- Optional `.semguard.yml` include/exclude rules are applied in both local and git-ref YAML extraction.
- Invalid semantic YAML now raises user-facing errors with source context instead of raw `KeyError` tracebacks.

## Example project

An example latest-spec dbt project lives in [examples/ecommerce_dbt_project](examples/ecommerce_dbt_project).

## Documentation

- [Contract spec](docs/contract-spec.md)
- [How to use and explain dbt-semguard](docs/how-to-use.md)
- [Severity rules](docs/severity-rules.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)

## License

This project is open source under the MIT License. See [LICENSE](LICENSE).
