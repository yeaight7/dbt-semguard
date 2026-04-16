# Changelog

## v0.1.0 - 2026-04-17

Initial public release.

### Added

- CLI commands for `extract`, `diff`, and `check`
- Latest-spec YAML extraction for semantic models, model-local metrics, and top-level advanced metrics
- Explicit manifest ingestion path normalized into the same semantic contract
- Deterministic semantic diffing with `breaking`, `risky`, and `safe` classifications
- Text, Markdown, and JSON reporting
- Checkout-free git ref comparison for YAML-based diffs
- Composite GitHub Action that writes a workflow summary, uploads a JSON artifact, and enforces a severity threshold
- Example dbt project, docs, and automated tests

### Current limits

- Manifest support targets a narrow explicit artifact shape in `v0.1`
- No legacy Semantic Layer YAML support yet
- No rename inference or migration metadata
- No PR comment orchestration yet
