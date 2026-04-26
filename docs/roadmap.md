# Roadmap

## Near term (v0.5.2 / v0.6.0)

- Implement advisory-only mode (`fail-on: none`).
- Normalize filter expressions (ignoring whitespace and quote differences) to prevent cosmetic false positives.
- Add direction-sensitive severity for time granularity changes (destructive vs non-destructive) and non-additive dimensions.
- Treat MetricFlow `measures` as first-class citizens in the semantic contract, rather than flattening them into simple metrics.
- Add inline GitHub Pull Request annotations using the Check Runs API.

## Later phases (v1.0 and distribution)

- Automated package publication to PyPI via GitHub Actions (Trusted Publishers).
- Evaluate migrating away from Pydantic v2 in favor of native Python `dataclasses` to drastically reduce package size and CLI cold-start time.
- Add "real-world" complex dbt project fixtures (with deep nesting, YAML anchors, and cross-references) for parser stress testing.
- Explicit rename and migration metadata.
- Config file support for severity overrides.
- Suggested remediation guidance in reports.
