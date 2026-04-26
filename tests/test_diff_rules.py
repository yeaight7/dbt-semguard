import json
from pathlib import Path

from dbt_semguard.diffing import FIELD_DIFF_POLICY, SEVERITY_BY_CODE, diff_contracts
from dbt_semguard.extractors import extract_contract_from_manifest, extract_contract_from_yaml_dir
from dbt_semguard.models import DimensionContract, EntityContract, MetricContract, SemanticContract, SemanticModelContract
from dbt_semguard.reporting import build_report


FIXTURES = Path(__file__).parent / "fixtures"


def test_diff_classifies_breaking_and_risky_changes():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    head = extract_contract_from_yaml_dir(FIXTURES / "projects" / "breaking_change")

    report = build_report(diff_contracts(base, head))

    codes = {(change.code, change.severity) for change in report.changes}
    assert ("metric.simple.agg_changed", "breaking") in codes
    assert ("metric.ratio.denominator_changed", "breaking") in codes
    assert ("dimension.removed", "breaking") in codes
    assert ("dimension.granularity_changed", "risky") in codes
    assert report.highest_severity == "breaking"
    assert report.blocking is True


def test_diff_ignores_description_only_changes():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    head = extract_contract_from_yaml_dir(FIXTURES / "projects" / "safe_change")

    report = build_report(diff_contracts(base, head))

    assert report.changes == []
    assert report.highest_severity == "safe"
    assert report.blocking is False


def test_diff_classifies_additions_filter_changes_and_label_changes():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    head = extract_contract_from_yaml_dir(FIXTURES / "projects" / "risky_change")

    report = build_report(diff_contracts(base, head))

    codes = {(change.code, change.severity) for change in report.changes}
    assert ("entity.added", "risky") in codes
    assert ("dimension.added", "risky") in codes
    assert ("metric.added", "risky") in codes
    assert ("metric.filter_changed", "risky") in codes
    assert ("metric.label_changed", "risky") in codes
    assert report.highest_severity == "risky"
    assert report.blocking is False


def test_diff_detects_semantic_time_and_non_additive_changes():
    base = SemanticContract(
        semantic_models={
            "orders": SemanticModelContract(name="orders", model_name="fct_orders", agg_time_dimension="ordered_at")
        },
        metrics={
            "gross_revenue": MetricContract(
                name="gross_revenue",
                metric_type="simple",                agg="sum",
                expr="order_total",
                agg_time_dimension="ordered_at",
                non_additive_dimension={"name": "ordered_at", "window_choice": "min"},
                owner_model="orders",
            )
        },
    )
    head = SemanticContract(
        semantic_models={
            "orders": SemanticModelContract(name="orders", model_name="fct_orders", agg_time_dimension="booked_at")
        },
        metrics={
            "gross_revenue": MetricContract(
                name="gross_revenue",
                metric_type="simple",                agg="sum",
                expr="order_total",
                agg_time_dimension="booked_at",
                non_additive_dimension={"name": "booked_at", "window_choice": "max"},
                owner_model="returns",
            )
        },
    )

    report = build_report(diff_contracts(base, head))

    codes = {(change.code, change.severity) for change in report.changes}
    assert ("semantic_model.agg_time_dimension_changed", "risky") in codes
    assert ("metric.agg_time_dimension_changed", "risky") in codes
    assert ("metric.simple.non_additive_dimension_changed", "breaking") in codes
    assert ("metric.owner_model_changed", "breaking") in codes


def test_diff_detects_derived_metric_expr_changes():
    base = SemanticContract(
        metrics={
            "revenue_delta": MetricContract(
                name="revenue_delta",
                metric_type="derived",                expr="current_revenue - prior_revenue",
                input_metrics=["current_revenue", "prior_revenue"],
            )
        }
    )
    head = SemanticContract(
        metrics={
            "revenue_delta": MetricContract(
                name="revenue_delta",
                metric_type="derived",                expr="current_revenue + prior_revenue",
                input_metrics=["current_revenue", "prior_revenue"],
            )
        }
    )

    report = build_report(diff_contracts(base, head))

    codes = {(change.code, change.severity) for change in report.changes}
    assert ("metric.derived.expr_changed", "breaking") in codes


def test_diff_attaches_source_location_to_change_records():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    head = extract_contract_from_yaml_dir(FIXTURES / "projects" / "breaking_change")

    changes = diff_contracts(base, head)
    agg_change = next(change for change in changes if change.code == "metric.simple.agg_changed")
    removed_dimension = next(change for change in changes if change.code == "dimension.removed")

    assert agg_change.source is not None
    assert agg_change.source.file == "models/orders.yml"
    assert agg_change.source.line == 21
    assert removed_dimension.source is not None
    assert removed_dimension.source.file == "models/orders.yml"
    assert removed_dimension.source.line == 21


def test_diff_detects_entity_and_dimension_expression_changes():
    base = SemanticContract(
        semantic_models={
            "orders": SemanticModelContract(
                name="orders",
                model_name="fct_orders",
                entities={"customer": EntityContract(name="customer", type="foreign", expr="customer_id")},
                dimensions={"country": DimensionContract(name="country", type="categorical", expr="country_code")},
            )
        }
    )
    head = SemanticContract(
        semantic_models={
            "orders": SemanticModelContract(
                name="orders",
                model_name="fct_orders",
                entities={"customer": EntityContract(name="customer", type="foreign", expr="customer_uuid")},
                dimensions={"country": DimensionContract(name="country", type="categorical", expr="country_name")},
            )
        }
    )
    report = build_report(diff_contracts(base, head))

    entity_change = next(change for change in report.changes if change.code == "entity.expr_changed")
    dimension_change = next(change for change in report.changes if change.code == "dimension.expr_changed")

    assert entity_change.severity == "breaking"
    assert entity_change.message == (
        "Entity `customer` in semantic model `orders` changed expression from `customer_id` to `customer_uuid`."
    )
    assert dimension_change.severity == "breaking"
    assert dimension_change.message == (
        "Dimension `country` in semantic model `orders` changed expression from `country_code` to `country_name`."
    )


def test_yaml_and_manifest_equivalent_filter_changes_produce_same_findings(tmp_path: Path):
    base_yaml_dir = FIXTURES / "projects" / "base"
    head_yaml_dir = tmp_path / "head_yaml"
    (head_yaml_dir / "models").mkdir(parents=True)
    head_yaml = (base_yaml_dir / "models" / "orders.yml").read_text(encoding="utf-8").replace(
        "filter: order_status = 'completed'",
        "filter: order_status in ('completed', 'refunded')",
    )
    (head_yaml_dir / "models" / "orders.yml").write_text(head_yaml, encoding="utf-8")

    base_manifest_path = FIXTURES / "manifest" / "base_semantic_manifest.json"
    head_manifest_path = tmp_path / "head_semantic_manifest.json"
    head_manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))
    head_manifest["metrics"][0]["filter"] = {"where_sql_template": "order_status in ('completed', 'refunded')"}
    head_manifest_path.write_text(json.dumps(head_manifest), encoding="utf-8")

    yaml_changes = diff_contracts(
        extract_contract_from_yaml_dir(base_yaml_dir),
        extract_contract_from_yaml_dir(head_yaml_dir),
    )
    manifest_changes = diff_contracts(
        extract_contract_from_manifest(base_manifest_path),
        extract_contract_from_manifest(head_manifest_path),
    )

    assert _normalized_changes(yaml_changes) == _normalized_changes(manifest_changes)


def test_yaml_and_manifest_equivalent_entity_expression_changes_produce_same_findings(tmp_path: Path):
    base_yaml_dir = tmp_path / "yaml_base"
    head_yaml_dir = tmp_path / "yaml_head"
    for project_dir in (base_yaml_dir, head_yaml_dir):
        (project_dir / "models").mkdir(parents=True)

    (base_yaml_dir / "models" / "orders.yml").write_text(
        _semantic_expr_project_yaml(customer_expr="customer_id", country_expr="country_code"),
        encoding="utf-8",
    )
    (head_yaml_dir / "models" / "orders.yml").write_text(
        _semantic_expr_project_yaml(customer_expr="customer_uuid", country_expr="country_code"),
        encoding="utf-8",
    )

    base_manifest_path = tmp_path / "base_semantic_manifest.json"
    head_manifest_path = tmp_path / "head_semantic_manifest.json"
    base_manifest_path.write_text(
        json.dumps(_semantic_expr_manifest(customer_expr="customer_id", country_expr="country_code")),
        encoding="utf-8",
    )
    head_manifest_path.write_text(
        json.dumps(_semantic_expr_manifest(customer_expr="customer_uuid", country_expr="country_code")),
        encoding="utf-8",
    )

    yaml_changes = diff_contracts(
        extract_contract_from_yaml_dir(base_yaml_dir),
        extract_contract_from_yaml_dir(head_yaml_dir),
    )
    manifest_changes = diff_contracts(
        extract_contract_from_manifest(base_manifest_path),
        extract_contract_from_manifest(head_manifest_path),
    )

    assert _normalized_changes(yaml_changes) == _normalized_changes(manifest_changes)


def test_field_diff_policy_accounts_for_all_supported_contract_fields():
    model_types = {
        "SemanticContract": SemanticContract,
        "SemanticModelContract": SemanticModelContract,
        "EntityContract": EntityContract,
        "DimensionContract": DimensionContract,
        "MetricContract": MetricContract,
    }

    for model_name, model_type in model_types.items():
        policy = FIELD_DIFF_POLICY[model_name]
        assert set(policy) == set(model_type.__dataclass_fields__)

        for rule in policy.values():
            if isinstance(rule, str):
                assert rule in SEVERITY_BY_CODE
            elif isinstance(rule, dict):
                for code in rule.values():
                    assert code in SEVERITY_BY_CODE


def test_diff_detects_cumulative_metric_semantic_changes():
    base = SemanticContract(
        metrics={
            "revenue_mtd": MetricContract(
                name="revenue_mtd",
                metric_type="cumulative",
                input_metric="revenue_daily",
                window="30d",
                grain_to_date="month",
                period_agg="sum",
            )
        }
    )
    head = SemanticContract(
        metrics={
            "revenue_mtd": MetricContract(
                name="revenue_mtd",
                metric_type="cumulative",
                input_metric="revenue_weekly",
                window="60d",
                grain_to_date="quarter",
                period_agg="avg",
            )
        }
    )

    report = build_report(diff_contracts(base, head))
    codes = {(change.code, change.severity) for change in report.changes}

    assert ("metric.cumulative.input_metric_changed", "breaking") in codes
    assert ("metric.cumulative.window_changed", "risky") in codes
    assert ("metric.cumulative.grain_to_date_changed", "risky") in codes
    assert ("metric.cumulative.period_agg_changed", "breaking") in codes


def test_diff_detects_conversion_metric_semantic_changes():
    base = SemanticContract(
        metrics={
            "signup_conversion": MetricContract(
                name="signup_conversion",
                metric_type="conversion",
                entity="user",
                calculation="conversion_rate",
                base_metric="signups",
                conversion_metric="paid_signups",
                constant_properties='[{"base_property": "plan", "conversion_property": "plan"}]',
            )
        }
    )
    head = SemanticContract(
        metrics={
            "signup_conversion": MetricContract(
                name="signup_conversion",
                metric_type="conversion",
                entity="account",
                calculation="conversions",
                base_metric="registrations",
                conversion_metric="activated_users",
                constant_properties='[{"base_property": "region", "conversion_property": "region"}]',
            )
        }
    )

    report = build_report(diff_contracts(base, head))
    codes = {(change.code, change.severity) for change in report.changes}

    assert ("metric.conversion.entity_changed", "breaking") in codes
    assert ("metric.conversion.calculation_changed", "breaking") in codes
    assert ("metric.conversion.base_metric_changed", "breaking") in codes
    assert ("metric.conversion.conversion_metric_changed", "breaking") in codes
    assert ("metric.conversion.constant_properties_changed", "risky") in codes


def test_yaml_and_manifest_equivalent_cumulative_changes_produce_same_findings(tmp_path: Path):
    base_yaml_dir = tmp_path / "yaml_cumulative_base"
    head_yaml_dir = tmp_path / "yaml_cumulative_head"
    for project_dir in (base_yaml_dir, head_yaml_dir):
        (project_dir / "models").mkdir(parents=True)

    (base_yaml_dir / "models" / "orders.yml").write_text(_advanced_metric_project_yaml(window="30d"), encoding="utf-8")
    (head_yaml_dir / "models" / "orders.yml").write_text(_advanced_metric_project_yaml(window="60d"), encoding="utf-8")

    base_manifest_path = tmp_path / "cumulative_base_semantic_manifest.json"
    head_manifest_path = tmp_path / "cumulative_head_semantic_manifest.json"
    base_manifest_path.write_text(json.dumps(_advanced_metric_manifest(window="30d")), encoding="utf-8")
    head_manifest_path.write_text(json.dumps(_advanced_metric_manifest(window="60d")), encoding="utf-8")

    yaml_changes = diff_contracts(
        extract_contract_from_yaml_dir(base_yaml_dir),
        extract_contract_from_yaml_dir(head_yaml_dir),
    )
    manifest_changes = diff_contracts(
        extract_contract_from_manifest(base_manifest_path),
        extract_contract_from_manifest(head_manifest_path),
    )

    assert _normalized_changes(yaml_changes) == _normalized_changes(manifest_changes)


def test_yaml_and_manifest_equivalent_conversion_changes_produce_same_findings(tmp_path: Path):
    base_yaml_dir = tmp_path / "yaml_conversion_base"
    head_yaml_dir = tmp_path / "yaml_conversion_head"
    for project_dir in (base_yaml_dir, head_yaml_dir):
        (project_dir / "models").mkdir(parents=True)

    (base_yaml_dir / "models" / "orders.yml").write_text(
        _advanced_metric_project_yaml(base_metric="signups", conversion_metric="paid_signups"),
        encoding="utf-8",
    )
    (head_yaml_dir / "models" / "orders.yml").write_text(
        _advanced_metric_project_yaml(base_metric="registrations", conversion_metric="activated_users"),
        encoding="utf-8",
    )

    base_manifest_path = tmp_path / "conversion_base_semantic_manifest.json"
    head_manifest_path = tmp_path / "conversion_head_semantic_manifest.json"
    base_manifest_path.write_text(
        json.dumps(_advanced_metric_manifest(base_metric="signups", conversion_metric="paid_signups")),
        encoding="utf-8",
    )
    head_manifest_path.write_text(
        json.dumps(_advanced_metric_manifest(base_metric="registrations", conversion_metric="activated_users")),
        encoding="utf-8",
    )

    yaml_changes = diff_contracts(
        extract_contract_from_yaml_dir(base_yaml_dir),
        extract_contract_from_yaml_dir(head_yaml_dir),
    )
    manifest_changes = diff_contracts(
        extract_contract_from_manifest(base_manifest_path),
        extract_contract_from_manifest(head_manifest_path),
    )

    assert _normalized_changes(yaml_changes) == _normalized_changes(manifest_changes)


def _normalized_changes(changes):
    return sorted((change.code, change.severity, change.path, change.before, change.after) for change in changes)


def _semantic_expr_project_yaml(*, customer_expr: str, country_expr: str) -> str:
    return f"""models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    columns:
      - name: customer_key
        expr: {customer_expr}
        entity:
          name: customer
          type: foreign
      - name: country_key
        expr: {country_expr}
        dimension:
          name: country
          type: categorical
    metrics:
      - name: gross_revenue
        type: simple
        agg: sum
        expr: order_total
"""


def _semantic_expr_manifest(*, customer_expr: str, country_expr: str) -> dict:
    return {
        "semantic_models": [
            {
                "name": "orders",
                "defaults": {},
                "node_relation": {"alias": "fct_orders"},
                "entities": [{"name": "customer", "type": "foreign", "expr": customer_expr}],
                "dimensions": [{"name": "country", "type": "categorical", "expr": country_expr}],
                "measures": [{"name": "gross_revenue", "agg": "sum", "expr": "order_total"}],
            }
        ],
        "metrics": [
            {
                "name": "gross_revenue",
                "type": "simple",
                "type_params": {
                    "measure": {"name": "gross_revenue"},
                    "metric_aggregation_params": {"semantic_model": "orders", "agg": "sum"},
                },
            }
        ],
        "project_configuration": {"time_spines": [], "time_spine_table_configurations": []},
    }


def _advanced_metric_project_yaml(*, window: str = "30d", base_metric: str = "signups", conversion_metric: str = "paid_signups") -> str:
    return f"""models:
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
    window: {window}
    grain_to_date: month
    period_agg: sum
  - name: signup_conversion
    type: conversion
    entity: user
    calculation: conversion_rate
    base_metric: {base_metric}
    conversion_metric: {conversion_metric}
    constant_properties:
      - base_property: plan
        conversion_property: plan
"""


def _advanced_metric_manifest(*, window: str = "30d", base_metric: str = "signups", conversion_metric: str = "paid_signups") -> dict:
    return {
        "semantic_models": [
            {
                "name": "orders",
                "defaults": {"agg_time_dimension": "ordered_at"},
                "node_relation": {"alias": "fct_orders"},
                "entities": [{"name": "user", "type": "primary", "expr": "user_id"}],
                "dimensions": [{"name": "ordered_at", "type": "time", "expr": "ordered_at", "type_params": {"time_granularity": "day"}}],
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
                    "cumulative_type_params": {"window": window, "grain_to_date": "month", "period_agg": "sum"},
                },
            },
            {
                "name": "signup_conversion",
                "type": "conversion",
                "type_params": {
                    "conversion_type_params": {
                        "entity": "user",
                        "calculation": "conversion_rate",
                        "base_measure": base_metric,
                        "conversion_measure": conversion_metric,
                        "constant_properties": [{"base_property": "plan", "conversion_property": "plan"}],
                    }
                },
            },
        ],
        "project_configuration": {"time_spines": [], "time_spine_table_configurations": []},
    }
