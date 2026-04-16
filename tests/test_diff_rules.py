from pathlib import Path

from dbt_semguard.diffing import diff_contracts
from dbt_semguard.extractors import extract_contract_from_yaml_dir
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
