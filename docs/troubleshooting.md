# Troubleshooting

## Git ref mode fails on CI

If `--base-ref` / `--head-ref` comparisons fail in GitHub Actions, check that the repository was fetched with enough history.

Recommended checkout settings:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
```

Also verify that the base and head refs still exist locally before running the action.

## YAML parsing or validation errors

`dbt-semguard` reports YAML validation failures with file and line context when it can.

If a YAML run fails:

- read the reported file and line first
- check required semantic fields such as entities, dimensions, and measures
- verify indentation and YAML anchors/aliases expand to valid structures

## PR comments do not appear on forked pull requests

On forked pull requests, the default `GITHUB_TOKEN` for the `pull_request` event is often read-only.

That means `pr-comment: true` may skip comment publishing even though the semantic diff still runs. The action is expected to continue without failing the whole job for that permission issue.

## Invalid `fail-on` values

The GitHub Action accepts only these values for `fail-on`:

- `breaking`
- `risky`
- `safe`

If you pass anything else, the action now fails early with a direct configuration error instead of a later internal exception.

## Wrong manifest artifact

Manifest mode expects dbt `semantic_manifest.json`, not the general-purpose dbt `manifest.json`.

If you pass `manifest.json`, switch the workflow to the semantic artifact or use YAML/git-ref mode instead.

## Zero semantic changes

When no semantic changes are detected, the Markdown report and `$GITHUB_STEP_SUMMARY` explicitly include:

```md
## dbt-semguard report

No semantic changes detected.

Status: passing
```
