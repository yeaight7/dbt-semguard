# Changelog

## v0.5.3 - 2026-04-26

### Fixed

- Fixed the public GitHub Action `pr-comment: true` path by aligning `action.yml` with the `semguard comment-pr` parser for `--head-sha` and `--report-json`.
- Made `semguard comment-pr` accept PR-comment-only, check-annotation-only, and combined input shapes while rejecting partial argument pairs with clear exit-code-2 errors.
- Replaced silent check-run permission skips with a non-fatal warning that points users to `checks: write` and fork PR token limitations.

### Changed

- Documented PyPI as the primary install path and kept GitHub tag installation as the secondary option.
- Added release-publish test execution before building and publishing distributions.
- Updated GitHub Action usage documentation to include `checks: write` for inline check-run annotations.

## v0.5.2 - 2026-04-26

### Added

- Native support for dbt MetricFlow `measures` as first-class citizens in extraction and diffing (`MeasureContract`).
- Support for `fail-on: none` advisory mode.
- Inline code annotations on GitHub PRs via the Check Runs API.
- Automated PyPI publishing workflow (`publish.yml`) using OIDC Trusted Publishers.

### Changed

- Replaced Pydantic with standard library `dataclasses` to drastically reduce package size and CLI cold-start times.
- Implemented direction-sensitive diffing for granularity changes (e.g., coarsening time granularity is `breaking`, fining it is `risky`).
- Improved SQL filter normalization to ignore whitespace, quotes, and case.
- Maintained strict backward compatibility with existing extracted JSON contracts during the Pydantic migration.

## v0.5.1 - 2026-04-26

### Added

- Added `SECURITY.md` with GitHub Security Advisories guidance and email fallback reporting
- Added `CONTRIBUTING.md` with Python 3.11+ setup, pinned dev installation, and test commands
- Added `docs/troubleshooting.md` for shallow clone, YAML validation, fork PR token, `fail-on`, and `semantic_manifest.json` issues
- Added `requirements-dev.txt` so contributor and CI environments can install pinned dev dependencies reproducibly

### Changed

- Updated `action.yml` input descriptions to document accepted `fail-on` and `pr-comment-mode` values directly in the action surface
- Action report files now use an isolated temp directory and artifact-derived basename instead of hardcoded workspace filenames
- CI now installs from `requirements-dev.txt` before editable package install
- README and usage docs now target `v0.5.1`, document `pr-comment-mode`, zero-change behavior, and show example Markdown/JSON output

### Reliability

- Action execution now validates invalid `fail-on` values early with a direct error message
- Zero-change reports remain explicit in the workflow summary and Markdown artifact with `No semantic changes detected.` and `Status: passing`

## v0.5.0 - 2026-04-26

### Added

- Added a dedicated internal action runner that generates JSON, Markdown, workflow summary text, and structured action outputs in one pass
- Added composite action outputs for `highest-severity`, `blocking`, `breaking-count`, `risky-count`, and `safe-count`
- Added packaging metadata in `pyproject.toml`, including classifiers, keywords, and project URLs

### Changed

- Hardened `action.yml` against shell injection by mapping GitHub expressions into `env:` and consuming only native shell variables inside `run:` blocks
- Artifact upload now runs with `if: always()` and warns instead of failing when report files are unavailable after an earlier error
- README and usage docs now target `v0.5.0` and document action outputs for downstream CI consumers

### Security and reliability

- Fixed the remaining composite action shell injection risk caused by embedding `${{ inputs.* }}` and `${{ github.* }}` directly inside Bash scripts
- Preserved report artifacts and action outputs for blocking semantic diffs before the enforcement step fails the job

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
