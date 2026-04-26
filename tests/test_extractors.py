import json
from pathlib import Path

import pytest

from dbt_semguard.extractors import extract_contract_from_manifest, extract_contract_from_yaml_dir


FIXTURES = Path(__file__).parent / "fixtures"


def test_yaml_extractor_builds_latest_spec_contract():
    contract = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")

    assert sorted(contract.semantic_models) == ["orders"]
    assert sorted(contract.metrics) == ["aov", "gross_revenue", "order_count"]
    model = contract.semantic_models["orders"]
    assert model.model_name == "fct_orders"
    assert model.agg_time_dimension == "ordered_at"
    assert model.entities["order"].type == "primary"
    assert model.entities["customer"].expr == "customer_id"
    assert model.dimensions["ordered_at"].granularity == "day"
    assert model.dimensions["country"].type == "categorical"
    assert contract.metrics["gross_revenue"].agg == "sum"
    assert contract.metrics["gross_revenue"].filter == "order_status = 'completed'"
    assert contract.metrics["gross_revenue"].owner_model == "orders"
    assert contract.metrics["aov"].numerator == "gross_revenue"
    assert contract.metrics["aov"].denominator == "order_count"
    assert model.source is not None
    assert model.source.file == "models/orders.yml"
    assert model.source.line == 3
    assert model.entities["order"].source is not None
    assert model.entities["order"].source.line == 9
    assert model.dimensions["ordered_at"].source is not None
    assert model.dimensions["ordered_at"].source.line == 18
    assert contract.metrics["gross_revenue"].source is not None
    assert contract.metrics["gross_revenue"].source.line == 24
    assert contract.metrics["aov"].source is not None
    assert contract.metrics["aov"].source.line == 36


def test_yaml_extractor_builds_legacy_spec_contract_equivalent_to_latest_spec():
    latest_contract = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    legacy_contract = extract_contract_from_yaml_dir(FIXTURES / "projects" / "legacy_base")

    assert legacy_contract.semantic_dump() == latest_contract.semantic_dump()
    assert legacy_contract.semantic_models["orders"].source is not None
    assert legacy_contract.semantic_models["orders"].source.file == "models/orders.yml"
    assert legacy_contract.semantic_models["orders"].source.line == 2
    assert legacy_contract.semantic_models["orders"].entities["order"].source is not None
    assert legacy_contract.semantic_models["orders"].entities["order"].source.line == 7
    assert legacy_contract.metrics["gross_revenue"].source is not None
    assert legacy_contract.metrics["gross_revenue"].source.line == 33


def test_yaml_extractor_ignores_cosmetic_metadata():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    safe = extract_contract_from_yaml_dir(FIXTURES / "projects" / "safe_change")

    assert safe == base


def test_manifest_extractor_matches_semantic_manifest_fixture():
    manifest_contract = extract_contract_from_manifest(FIXTURES / "manifest" / "base_semantic_manifest.json")
    expected = json.loads((FIXTURES / "contracts" / "base_contract.json").read_text())

    assert manifest_contract.model_dump() == expected

def test_manifest_extractor_rejects_plain_dbt_manifest_artifact(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"},
                "nodes": {},
                "metrics": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="semantic_manifest.json"):
        extract_contract_from_manifest(manifest_path)


def test_manifest_extractor_rejects_unresolvable_simple_metric_measure(tmp_path: Path):
    manifest_path = tmp_path / "semantic_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "semantic_models": [
                    {
                        "name": "orders",
                        "defaults": {"agg_time_dimension": "ordered_at"},
                        "node_relation": {"alias": "fct_orders"},
                        "entities": [],
                        "dimensions": [],
                        "measures": [],
                    }
                ],
                "metrics": [
                    {
                        "name": "gross_revenue",
                        "type": "simple",
                        "type_params": {
                            "measure": {"name": "gross_revenue"},
                            "metric_aggregation_params": {
                                "semantic_model": "orders",
                                "agg": "sum",
                                "agg_time_dimension": "ordered_at",
                            },
                        },
                    }
                ],
                "project_configuration": {"time_spines": [], "time_spine_table_configurations": []},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="gross_revenue"):
        extract_contract_from_manifest(manifest_path)


def test_yaml_extractor_supports_cumulative_and_conversion_metrics(tmp_path: Path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    agg_time_dimension: ordered_at
    columns:
      - name: ordered_at
        granularity: day
        dimension:
          type: time
      - name: user_id
        entity:
          type: primary
          name: user
    metrics:
      - name: revenue_daily
        type: simple
        agg: sum
        expr: order_total
      - name: signups
        type: simple
        agg: count
        expr: 1
      - name: paid_signups
        type: simple
        agg: count
        expr: 1

metrics:
  - name: revenue_mtd
    type: cumulative
    input_metric: revenue_daily
    window: 30d
    grain_to_date: month
    period_agg: sum
  - name: signup_conversion
    type: conversion
    entity: user
    calculation: conversion_rate
    base_metric: signups
    conversion_metric: paid_signups
    constant_properties:
      - base_property: plan
        conversion_property: plan
""",
        encoding="utf-8",
    )

    contract = extract_contract_from_yaml_dir(tmp_path)

    revenue_mtd = contract.metrics["revenue_mtd"]
    signup_conversion = contract.metrics["signup_conversion"]

    assert revenue_mtd.metric_type == "cumulative"
    assert revenue_mtd.input_metric == "revenue_daily"
    assert revenue_mtd.window == "30d"
    assert revenue_mtd.grain_to_date == "month"
    assert revenue_mtd.period_agg == "sum"

    assert signup_conversion.metric_type == "conversion"
    assert signup_conversion.entity == "user"
    assert signup_conversion.calculation == "conversion_rate"
    assert signup_conversion.base_metric == "signups"
    assert signup_conversion.conversion_metric == "paid_signups"
    assert signup_conversion.constant_properties == '[{"base_property": "plan", "conversion_property": "plan"}]'


def test_yaml_extractor_supports_legacy_type_params_metrics(tmp_path: Path):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "orders.yml").write_text(
        """semantic_models:
  - name: orders
    model: ref('fct_orders')
    defaults:
      agg_time_dimension: ordered_at
    entities:
      - name: user
        type: primary
        expr: user_id
    dimensions:
      - name: ordered_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: revenue_daily
        agg: sum
        expr: order_total
      - name: signups
        agg: count
        expr: 1
      - name: paid_signups
        agg: count
        expr: 1

metrics:
  - name: revenue_daily
    type: simple
    type_params:
      measure: revenue_daily
      metric_aggregation_params:
        semantic_model: orders
        agg: sum
  - name: signups
    type: simple
    type_params:
      measure: signups
      metric_aggregation_params:
        semantic_model: orders
        agg: count
  - name: paid_signups
    type: simple
    type_params:
      measure: paid_signups
      metric_aggregation_params:
        semantic_model: orders
        agg: count
  - name: revenue_mtd
    type: cumulative
    type_params:
      measure: revenue_daily
      cumulative_type_params:
        window: 30d
        grain_to_date: month
        period_agg: sum
  - name: signup_conversion
    type: conversion
    type_params:
      conversion_type_params:
        entity: user
        calculation: conversion_rate
        base_measure: signups
        conversion_measure: paid_signups
        constant_properties:
          - base_property: plan
            conversion_property: plan
  - name: blended_revenue
    type: derived
    type_params:
      expr: revenue_daily + revenue_daily
      metrics:
        - name: revenue_daily
          alias: current_revenue
        - name: revenue_daily
          alias: previous_revenue
          offset_window: 7 days
""",
        encoding="utf-8",
    )

    contract = extract_contract_from_yaml_dir(tmp_path)

    revenue_daily = contract.metrics["revenue_daily"]
    revenue_mtd = contract.metrics["revenue_mtd"]
    signup_conversion = contract.metrics["signup_conversion"]
    blended_revenue = contract.metrics["blended_revenue"]

    assert revenue_daily.metric_type == "simple"
    assert revenue_daily.agg == "sum"
    assert revenue_daily.expr == "order_total"
    assert revenue_daily.owner_model == "orders"

    assert revenue_mtd.metric_type == "cumulative"
    assert revenue_mtd.input_metric == "revenue_daily"
    assert revenue_mtd.window == "30d"
    assert revenue_mtd.grain_to_date == "month"
    assert revenue_mtd.period_agg == "sum"

    assert signup_conversion.metric_type == "conversion"
    assert signup_conversion.entity == "user"
    assert signup_conversion.calculation == "conversion_rate"
    assert signup_conversion.base_metric == "signups"
    assert signup_conversion.conversion_metric == "paid_signups"
    assert signup_conversion.constant_properties == '[{"base_property": "plan", "conversion_property": "plan"}]'

    assert blended_revenue.metric_type == "derived"
    assert blended_revenue.expr == "revenue_daily + revenue_daily"
    assert blended_revenue.input_metrics == [
        '{"alias": "current_revenue", "name": "revenue_daily"}',
        '{"alias": "previous_revenue", "name": "revenue_daily", "offset_window": "7 days"}',
    ]


def test_manifest_extractor_supports_cumulative_and_conversion_metrics(tmp_path: Path):
    manifest_path = tmp_path / "semantic_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "semantic_models": [
                    {
                        "name": "orders",
                        "defaults": {"agg_time_dimension": "ordered_at"},
                        "node_relation": {"alias": "fct_orders"},
                        "entities": [{"name": "user", "type": "primary", "expr": "user_id"}],
                        "dimensions": [
                            {
                                "name": "ordered_at",
                                "type": "time",
                                "expr": "ordered_at",
                                "type_params": {"time_granularity": "day"},
                            }
                        ],
                        "measures": [
                            {"name": "revenue_daily", "agg": "sum", "expr": "order_total"},
                            {"name": "signups", "agg": "count", "expr": "1"},
                            {"name": "paid_signups", "agg": "count", "expr": "1"},
                        ],
                    }
                ],
                "metrics": [
                    {
                        "name": "revenue_daily",
                        "type": "simple",
                        "type_params": {
                            "measure": {"name": "revenue_daily"},
                            "metric_aggregation_params": {"semantic_model": "orders", "agg": "sum"},
                        },
                    },
                    {
                        "name": "signups",
                        "type": "simple",
                        "type_params": {
                            "measure": {"name": "signups"},
                            "metric_aggregation_params": {"semantic_model": "orders", "agg": "count"},
                        },
                    },
                    {
                        "name": "paid_signups",
                        "type": "simple",
                        "type_params": {
                            "measure": {"name": "paid_signups"},
                            "metric_aggregation_params": {"semantic_model": "orders", "agg": "count"},
                        },
                    },
                    {
                        "name": "revenue_mtd",
                        "type": "cumulative",
                        "type_params": {
                            "measure": {"name": "revenue_daily"},
                            "cumulative_type_params": {"window": "30d", "grain_to_date": "month", "period_agg": "sum"},
                        },
                    },
                    {
                        "name": "signup_conversion",
                        "type": "conversion",
                        "type_params": {
                            "conversion_type_params": {
                                "entity": "user",
                                "calculation": "conversion_rate",
                                "base_measure": "signups",
                                "conversion_measure": "paid_signups",
                                "constant_properties": [{"base_property": "plan", "conversion_property": "plan"}],
                            }
                        },
                    },
                ],
                "project_configuration": {"time_spines": [], "time_spine_table_configurations": []},
            }
        ),
        encoding="utf-8",
    )

    contract = extract_contract_from_manifest(manifest_path)

    revenue_mtd = contract.metrics["revenue_mtd"]
    signup_conversion = contract.metrics["signup_conversion"]

    assert revenue_mtd.metric_type == "cumulative"
    assert revenue_mtd.input_metric == "revenue_daily"
    assert revenue_mtd.window == "30d"
    assert revenue_mtd.grain_to_date == "month"
    assert revenue_mtd.period_agg == "sum"

    assert signup_conversion.metric_type == "conversion"
    assert signup_conversion.entity == "user"
    assert signup_conversion.calculation == "conversion_rate"
    assert signup_conversion.base_metric == "signups"
    assert signup_conversion.conversion_metric == "paid_signups"
    assert signup_conversion.constant_properties == '[{"base_property": "plan", "conversion_property": "plan"}]'


def test_yaml_extractor_scopes_to_project_dir_in_monorepo(tmp_path: Path):
    project_a = tmp_path / "dbt_project_a"
    project_b = tmp_path / "dbt_project_b"
    (project_a / "models").mkdir(parents=True)
    (project_b / "models").mkdir(parents=True)

    (project_a / "models" / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    metrics:
      - name: order_count
        type: simple
        agg: count
        expr: 1
""",
        encoding="utf-8",
    )
    (project_b / "models" / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    metrics:
      - name: order_count
        type: simple
        agg: sum
        expr: 1
""",
        encoding="utf-8",
    )

    contract = extract_contract_from_yaml_dir(project_a)

    assert contract.metrics["order_count"].agg == "count"


def test_yaml_extractor_uses_default_include_exclude_filters(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "misc").mkdir()
    (tmp_path / "models" / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
""",
        encoding="utf-8",
    )
    (tmp_path / "misc" / "extra.yml").write_text(
        """metrics:
  - name: ignored_metric
    type: simple
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )

    contract = extract_contract_from_yaml_dir(tmp_path)

    assert "ignored_metric" not in contract.metrics


def test_yaml_extractor_applies_semguard_include_exclude_overrides(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "misc").mkdir()
    (tmp_path / ".semguard.yml").write_text(
        """include:
  - misc/**/*.yml
exclude:
  - models/**
""",
        encoding="utf-8",
    )
    (tmp_path / "models" / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
""",
        encoding="utf-8",
    )
    (tmp_path / "misc" / "extra.yml").write_text(
        """metrics:
  - name: custom_metric
    type: simple
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )

    contract = extract_contract_from_yaml_dir(tmp_path)

    assert sorted(contract.semantic_models) == []
    assert sorted(contract.metrics) == ["custom_metric"]


def test_yaml_extractor_reports_metric_missing_name_with_context(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """metrics:
  - type: simple
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"missing required 'name'.*models/bad.yml:2"):
        extract_contract_from_yaml_dir(tmp_path)


def test_yaml_extractor_reports_metric_missing_type_with_context(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """metrics:
  - name: gross_revenue
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"missing required 'type'.*models/bad.yml:2"):
        extract_contract_from_yaml_dir(tmp_path)


def test_yaml_extractor_reports_entity_missing_type_with_context(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    columns:
      - name: order_id
        entity:
          name: order
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"entity 'order'.*missing required 'type'.*models/bad.yml:8"):
        extract_contract_from_yaml_dir(tmp_path)


def test_yaml_extractor_reports_dimension_missing_type_with_context(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    columns:
      - name: ordered_at
        granularity: day
        dimension:
          name: ordered_at
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"dimension 'ordered_at'.*missing required 'type'.*models/bad.yml:9"):
        extract_contract_from_yaml_dir(tmp_path)


def test_yaml_extractor_reports_non_mapping_semantic_model_payload(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"semantic_model' must be a mapping.*models/bad.yml:3"):
        extract_contract_from_yaml_dir(tmp_path)


def test_yaml_extractor_reports_malformed_yaml_with_context(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "bad.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model: [
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Malformed YAML in 'models/bad.yml:4'"):
        extract_contract_from_yaml_dir(tmp_path)
