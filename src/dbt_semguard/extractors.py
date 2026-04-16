from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml

from dbt_semguard.git_utils import load_yaml_documents_from_git_ref
from dbt_semguard.models import (
    DimensionContract,
    EntityContract,
    MetricContract,
    SemanticContract,
    SemanticModelContract,
)


def extract_contract_from_yaml_dir(project_dir: str | Path) -> SemanticContract:
    root = Path(project_dir)
    documents = [
        (str(path.relative_to(root)), path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    ]
    return _build_contract_from_yaml_documents(documents)


def extract_contract_from_git_ref(project_dir: str | Path, git_ref: str) -> SemanticContract:
    return _build_contract_from_yaml_documents(load_yaml_documents_from_git_ref(project_dir, git_ref))


def extract_contract_from_manifest(manifest_path: str | Path) -> SemanticContract:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if "semantic_models" not in payload:
        raise ValueError("manifest is missing required 'semantic_models' section")

    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}

    for node in _mapping_values(payload.get("semantic_models", {})):
        name = node["name"]
        semantic_models[name] = SemanticModelContract(
            name=name,
            model_name=node["model_name"],
            agg_time_dimension=node.get("agg_time_dimension"),
            entities={
                entity["name"]: EntityContract(
                    name=entity["name"],
                    type=entity["type"],
                    expr=entity.get("expr") or entity["name"],
                )
                for entity in node.get("entities", [])
            },
            dimensions={
                dimension["name"]: DimensionContract(
                    name=dimension["name"],
                    type=dimension["type"],
                    expr=dimension.get("expr") or dimension["name"],
                    granularity=dimension.get("granularity"),
                )
                for dimension in node.get("dimensions", [])
            },
        )

    for node in _mapping_values(payload.get("metrics", {})):
        metric = _build_metric_contract(node, owner_model=node.get("owner_model"))
        metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)


def _build_contract_from_yaml_documents(documents: Iterable[tuple[str, str]]) -> SemanticContract:
    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}

    for _, content in documents:
        for payload in yaml.safe_load_all(content):
            if not isinstance(payload, dict):
                continue

            for model in payload.get("models", []) or []:
                if not isinstance(model, dict):
                    continue
                semantic_block = model.get("semantic_model")
                if not isinstance(semantic_block, dict) or semantic_block.get("enabled", True) is False:
                    continue

                semantic_name = semantic_block.get("name") or model["name"]
                contract = SemanticModelContract(
                    name=semantic_name,
                    model_name=model["name"],
                    agg_time_dimension=model.get("agg_time_dimension"),
                )

                for column in model.get("columns", []) or []:
                    if not isinstance(column, dict) or "name" not in column:
                        continue
                    _attach_column_semantics(contract, column)

                semantic_models[semantic_name] = contract

                for metric_payload in model.get("metrics", []) or []:
                    if not isinstance(metric_payload, dict):
                        continue
                    metric = _build_metric_contract(metric_payload, owner_model=semantic_name)
                    metrics[metric.name] = metric

            for metric_payload in payload.get("metrics", []) or []:
                if not isinstance(metric_payload, dict):
                    continue
                metric = _build_metric_contract(metric_payload, owner_model=None)
                metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)


def _attach_column_semantics(contract: SemanticModelContract, column: dict[str, Any]) -> None:
    column_name = column["name"]
    column_expr = column.get("expr") or column_name

    entity_payload = column.get("entity")
    if isinstance(entity_payload, dict):
        entity_name = entity_payload.get("name") or column_name
        contract.entities[entity_name] = EntityContract(
            name=entity_name,
            type=entity_payload["type"],
            expr=entity_payload.get("expr") or column_expr,
        )

    dimension_payload = column.get("dimension")
    if isinstance(dimension_payload, dict):
        dimension_name = dimension_payload.get("name") or column_name
        contract.dimensions[dimension_name] = DimensionContract(
            name=dimension_name,
            type=dimension_payload["type"],
            expr=dimension_payload.get("expr") or column_expr,
            granularity=column.get("granularity"),
        )


def _build_metric_contract(payload: dict[str, Any], owner_model: str | None) -> MetricContract:
    return MetricContract(
        name=payload["name"],
        type=payload["type"],
        label=payload.get("label"),
        agg=payload.get("agg"),
        expr=_normalize_value(payload.get("expr")),
        filter=_normalize_value(payload.get("filter")),
        agg_time_dimension=payload.get("agg_time_dimension"),
        numerator=_normalize_metric_ref(payload.get("numerator")),
        denominator=_normalize_metric_ref(payload.get("denominator")),
        input_metrics=_normalize_input_metrics(payload.get("input_metrics")),
        non_additive_dimension=payload.get("non_additive_dimension"),
        owner_model=owner_model,
    )


def _normalize_metric_ref(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if "name" in value:
            return str(value["name"])
        return json.dumps(value, sort_keys=True)
    return str(value)


def _normalize_input_metrics(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [json.dumps(value, sort_keys=True)]

    normalized: list[str] = []
    for item in value:
        if isinstance(item, dict) and "name" in item and set(item.keys()) == {"name"}:
            normalized.append(str(item["name"]))
        else:
            normalized.append(json.dumps(item, sort_keys=True))
    return normalized


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _mapping_values(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
