# Changelog

## v0.4.0 - 2026-04-24

### Added

- Added `.semguard.yml` YAML discovery configuration for `include` and `exclude` rules
- Added default YAML discovery safeguards to focus extraction on semantic directories and skip common non-project paths
- Added monorepo coverage tests for local YAML mode and checkout-free git ref mode scoped by `--project-dir`
- Added YAML validation tests for missing required metric/entity/dimension fields and malformed YAML

### Changed

- Git ref YAML extraction now scopes file listing to the selected `--project-dir` instead of scanning the full repository tree
- YAML extraction now raises user-facing validation errors with source-file context instead of surfacing raw `KeyError` exceptions
- CI now keeps pre-release smoke validation on `uses: ./`, while published-action smoke validation runs separately after release publication or manual dispatch
- README and usage docs now document monorepo `--project-dir` behavior, `.semguard.yml`, and `v0.4.0` migration notes

### Known limitations

- No `fail-on: none` advisory-only mode yet
- No allowlist for intentional semantic changes yet
- No inline PR annotations yet
- No PyPI publishing yet
- Manifest mode expects dbt `semantic_manifest.json`, not arbitrary `manifest.json`

## v0.3.0 - 2026-04-21

### Added

- Added breaking change detection for entity expression changes and dimension expression changes
- Added end-to-end support for cumulative metrics and conversion metrics in YAML and `semantic_manifest.json` extraction
- Added a field-coverage policy for the semantic contract so diffed, nested, and intentionally excluded fields are auditable in tests
- Added CI smoke coverage for the published action in manifest mode with hostile spaced paths

### Changed

- Refactored the diff engine to use declarative field comparators instead of ad hoc per-field branching
- Markdown and text reports now group multiple findings under the same semantic object for easier review
- Change messages now include more precise semantic object context, especially for entities and dimensions nested under semantic models

## v0.2.0 - 2026-04-17

Focused release for PR usability and source-level diagnostics.

### Added

- YAML extraction now captures best-effort `source.file` and `source.line` diagnostics for semantic models, entities, dimensions, and metrics
- Change records now carry source diagnostics through diffing and JSON output
- Markdown and text reports now append `file:line` context when available
- Added `semguard comment-pr` for sticky GitHub PR comment publishing
- Composite action can now publish or update a sticky PR comment with `pr-comment: true`

### Changed

- README and action examples now target `v0.2.0`
- Release coverage now explicitly documents diagnostics and PR comment support

## v0.1.1 - 2026-04-17

Marketplace packaging follow-up release.

### Fixed

- Composite action now installs from `github.action_path` instead of the caller workspace
- Added Marketplace branding metadata to `action.yml`
- Replaced local `uses: ./` consumer guidance with the published action ref
- Replaced broken Windows absolute README links with repo-relative links

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
