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

## What v0.4.0 Adds

`v0.4.0` focuses on analysis-scope correctness and parser robustness:

- strict monorepo scoping for `--project-dir` in git ref mode
- safe default include/exclude YAML discovery patterns
- optional `.semguard.yml` include/exclude overrides
- clearer YAML extraction errors with file/line context for invalid semantic payloads

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
