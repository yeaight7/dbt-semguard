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


def test_yaml_extractor_ignores_cosmetic_metadata():
    base = extract_contract_from_yaml_dir(FIXTURES / "projects" / "base")
    safe = extract_contract_from_yaml_dir(FIXTURES / "projects" / "safe_change")

    assert safe == base


def test_manifest_extractor_matches_contract_fixture():
    manifest_contract = extract_contract_from_manifest(FIXTURES / "manifest" / "base_manifest.json")
    expected = json.loads((FIXTURES / "contracts" / "base_contract.json").read_text())

    assert manifest_contract.model_dump(mode="json") == expected


def test_manifest_extractor_rejects_missing_sections(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"metrics": {}}))

    with pytest.raises(ValueError, match="semantic_models"):
        extract_contract_from_manifest(manifest_path)
