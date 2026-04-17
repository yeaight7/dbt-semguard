from pathlib import Path

from dbt_semguard.diffing import diff_contracts
from dbt_semguard.extractors import extract_contract_from_yaml_dir
from dbt_semguard.models import MetricContract, SemanticContract, SemanticModelContract
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
                type="simple",
                agg="sum",
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
                type="simple",
                agg="sum",
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
                type="derived",
                expr="current_revenue - prior_revenue",
                input_metrics=["current_revenue", "prior_revenue"],
            )
        }
    )
    head = SemanticContract(
        metrics={
            "revenue_delta": MetricContract(
                name="revenue_delta",
                type="derived",
                expr="current_revenue + prior_revenue",
                input_metrics=["current_revenue", "prior_revenue"],
            )
        }
    )

    report = build_report(diff_contracts(base, head))

    codes = {(change.code, change.severity) for change in report.changes}
    assert ("metric.derived.expr_changed", "breaking") in codes
