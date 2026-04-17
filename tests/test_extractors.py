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


def test_manifest_extractor_matches_semantic_manifest_fixture():
    manifest_contract = extract_contract_from_manifest(FIXTURES / "manifest" / "base_semantic_manifest.json")
    expected = json.loads((FIXTURES / "contracts" / "base_contract.json").read_text())

    assert manifest_contract.model_dump(mode="json") == expected


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
