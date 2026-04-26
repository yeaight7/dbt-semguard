# How To Use And Explain dbt-semguard

## What It Is

`dbt-semguard` is a semantic change detector for dbt Semantic Layer definitions.

Its job is not to tell you whether the YAML is formatted correctly. Its job is to tell you whether a PR changed the meaning of a metric or semantic model in a way that could surprise downstream users.

## What Problem It Solves

Many semantic changes are valid dbt changes but still risky business changes.

Examples:

- changing a measure from `sum` to `avg`
- removing a dimension used by BI users to slice a KPI
- changing a ratio numerator or denominator
- changing a filter so a metric includes or excludes different rows
- changing entity or grain semantics

Without a semantic diff, those changes can land in production looking like a normal refactor.

## How To Explain It Quickly

If you need to explain the project to a teammate, use one of these:

One sentence:

> `dbt-semguard` catches semantic breaking changes in dbt metrics before they land in production.

Slightly longer:

> It compares the Semantic Layer before and after a PR and reports whether the meaning of a metric changed, even if dbt still parses and CI still passes.

## How It Works

At a high level:

1. it reads two versions of the dbt semantic definition
2. it extracts a canonical semantic contract from each side
3. it diffs those contracts
4. it classifies each change as `breaking`, `risky`, or `safe`

It keeps the pieces that affect meaning and ignores cosmetic metadata.

## What v0.5.3 Adds

`v0.5.3` is a release-surface hardening release focused on making the public GitHub Action behavior match the documented interface.

- **PR comments and annotations:** the `pr-comment: true` action path now aligns with the `semguard comment-pr` CLI parser, including `--head-sha` and `--report-json`.
- **Argument validation:** `semguard comment-pr` now supports PR-comment-only, check-annotation-only, and combined modes, while rejecting incomplete argument pairs with clear configuration errors.
- **Permission diagnostics:** missing Check Runs API permissions now produce a non-fatal warning instead of silently skipping inline annotations.
- **Documentation:** PyPI is now documented as the primary install path, with GitHub tag installation kept as the secondary pinning option.
- **Release safety:** the PyPI publish workflow now runs the test suite before building and publishing distributions.

## What v0.5.2 Adds

`v0.5.2` is a massive architectural refactor focusing on performance, precision, and deeper platform integration:

- **Performance:** Pydantic was removed in favor of standard `dataclasses`, significantly reducing package size and CLI cold-start times.
- **Precision:** MetricFlow `measures` are now natively extracted and diffed, preventing false negatives for aggregation/expression changes. Diffing is now direction-sensitive (e.g. changing granularity). SQL filters are normalized.
- **Usability:** Added `fail-on: none` advisory mode and inline GitHub PR code annotations via the Check Runs API.
- **Distribution:** Added an automated PyPI publishing workflow.

## What v0.5.1 Adds

`v0.5.1` focuses on safer CI execution, clearer action behavior, and contributor hygiene:

- env-only composite action shell wiring for user-controlled inputs
- collision-safe report paths derived from the uploaded artifact name
- single-pass action report generation with structured outputs
- contributor, security, and troubleshooting docs for the public action surface

## When To Use Which Command

### `semguard diff`

Use `diff` when you want to inspect and understand semantic changes.

Examples:

```bash
semguard diff --base-ref main --head-ref HEAD --project-dir .
semguard diff --base-ref main --head-ref HEAD --project-dir analytics/dbt
semguard diff --base-contract base.json --head-contract head.json --format markdown
```

### `semguard check`

Use `check` when you want an automation-friendly exit code.

Example:

```bash
semguard check --base-ref main --head-ref HEAD --project-dir . --fail-on breaking
```

### `semguard extract`

Use `extract` when you want a stable JSON contract that can be stored, compared, or inspected later.

Example:

```bash
semguard extract --source yaml --project-dir . --output contract.json
```

## How To Interpret Severity

- `breaking`: meaning changed in a way that should usually block the PR
- `risky`: the change may be intentional, but it deserves human review
- `safe`: cosmetic-only changes that should not show up in the semantic diff

## Recommended Team Workflow

For a data team, the simplest rollout is:

1. run `semguard diff` locally while developing
2. add `semguard check --fail-on breaking` to CI
3. review risky changes explicitly in PRs
4. treat breaking changes as requiring migration planning or explicit sign-off
