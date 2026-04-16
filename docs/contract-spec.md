# dbt-semguard Contract Spec

`dbt-semguard` extracts dbt Semantic Layer inputs into a canonical contract and diffs only that contract. The goal is to compare business meaning, not YAML cosmetics.

## Canonical shape

```json
{
  "semantic_models": {
    "orders": {
      "name": "orders",
      "model_name": "fct_orders",
      "agg_time_dimension": "ordered_at",
      "entities": {
        "order": { "name": "order", "type": "primary", "expr": "order_id" }
      },
      "dimensions": {
        "ordered_at": {
          "name": "ordered_at",
          "type": "time",
          "expr": "ordered_at",
          "granularity": "day"
        }
      }
    }
  },
  "metrics": {
    "gross_revenue": {
      "name": "gross_revenue",
      "metric_type": "simple",
      "label": "Gross Revenue",
      "agg": "sum",
      "expr": "order_total",
      "filter": "order_status = 'completed'",
      "agg_time_dimension": null,
      "numerator": null,
      "denominator": null,
      "input_metrics": [],
      "non_additive_dimension": null,
      "owner_model": "orders"
    }
  }
}
```

## Included in equality

- Semantic model identity and backing dbt model name
- Model-level `agg_time_dimension`
- Entities and entity types
- Dimensions, dimension types, expressions, and granularity
- Metric type and type-specific parameters
- Metric filters
- Metric label
- Metric ownership for model-local simple metrics

## Excluded from equality

- Descriptions
- Docs blocks
- Comments
- Whitespace
- YAML ordering
- Tags and arbitrary metadata
- File paths and line numbers

## Supported inputs in v0.1

- Latest dbt Semantic Layer YAML spec
- Explicit `manifest.json` input
- Canonical contract JSON emitted by `semguard extract`

## Notes

- `v0.1` does not infer renames.
- Latest spec assumptions follow dbt docs updated April 16, 2026:
  - `semantic_model` lives under `models`
  - entities and dimensions live under `columns`
  - simple metrics live within the model
  - advanced metrics remain under top-level `metrics`
