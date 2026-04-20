# Severity Rules

`dbt-semguard` maps semantic changes into three severities.

## Breaking

These fail `semguard check` by default.

- `semantic_model.removed`
- `semantic_model.model_changed`
- `metric.owner_model_changed`
- `entity.removed`
- `entity.type_changed`
- `entity.expr_changed`
- `dimension.removed`
- `dimension.type_changed`
- `dimension.expr_changed`
- `metric.removed`
- `metric.type_changed`
- `metric.simple.agg_changed`
- `metric.simple.expr_changed`
- `metric.simple.non_additive_dimension_changed`
- `metric.ratio.numerator_changed`
- `metric.ratio.denominator_changed`
- `metric.derived.inputs_changed`
- `metric.derived.expr_changed`

## Risky

These warn by default and become blocking only if `--fail-on risky` or `--fail-on safe` is used.

- `semantic_model.added`
- `semantic_model.agg_time_dimension_changed`
- `entity.added`
- `dimension.added`
- `dimension.granularity_changed`
- `metric.added`
- `metric.filter_changed`
- `metric.label_changed`
- `metric.agg_time_dimension_changed`

## Safe

Safe changes do not appear in the semantic diff.

- Description-only edits
- Docs text changes
- YAML reordering
- Whitespace or comment changes

## Defaults

- Default threshold: `--fail-on breaking`
- No repo-level config file in `v0.3`
- No rename inference in `v0.3`
- `source` diagnostics and identity fields such as object names are intentionally excluded from semantic equality
