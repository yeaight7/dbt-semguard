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
    SourceLocation,
)

_SOURCE_LINE_KEY = "__semguard_source_line__"
_SOURCE_END_LINE_KEY = "__semguard_source_end_line__"
_SOURCE_KEY_LINES_KEY = "__semguard_source_key_lines__"


class _LineLoader(yaml.SafeLoader):
    pass


def _construct_mapping_with_lines(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[str, Any]:
    mapping = yaml.SafeLoader.construct_mapping(loader, node, deep=deep)
    key_lines = [key_node.start_mark.line + 1 for key_node, _ in node.value]
    mapping[_SOURCE_LINE_KEY] = min(key_lines) if key_lines else node.start_mark.line + 1
    mapping[_SOURCE_END_LINE_KEY] = node.end_mark.line + 1
    mapping[_SOURCE_KEY_LINES_KEY] = {
        key_node.value: key_node.start_mark.line + 1 for key_node, _ in node.value if isinstance(key_node.value, str)
    }
    return mapping


_LineLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_with_lines)


def extract_contract_from_yaml_dir(project_dir: str | Path) -> SemanticContract:
    root = Path(project_dir)
    documents = [
        (path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    ]
    return _build_contract_from_yaml_documents(documents)


def extract_contract_from_git_ref(project_dir: str | Path, git_ref: str) -> SemanticContract:
    return _build_contract_from_yaml_documents(load_yaml_documents_from_git_ref(project_dir, git_ref))


def extract_contract_from_manifest(manifest_path: str | Path) -> SemanticContract:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if _looks_like_plain_dbt_manifest(payload):
        raise ValueError(
            "Unsupported dbt manifest.json artifact. Pass a dbt semantic_manifest.json artifact instead."
        )
    if "semantic_models" not in payload or "metrics" not in payload:
        raise ValueError(
            "Manifest input must be a dbt semantic_manifest.json artifact with 'semantic_models' and 'metrics'."
        )
    if _looks_like_semantic_manifest_payload(payload):
        return _build_contract_from_semantic_manifest_payload(payload)
    return _build_contract_from_compact_manifest_payload(payload)


def _build_contract_from_compact_manifest_payload(payload: dict[str, Any]) -> SemanticContract:
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


def _build_contract_from_semantic_manifest_payload(payload: dict[str, Any]) -> SemanticContract:
    if "project_configuration" not in payload:
        raise ValueError("semantic_manifest.json is missing required 'project_configuration' section")

    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}
    measures_by_model: dict[str, dict[str, dict[str, Any]]] = {}
    model_default_agg_time_dimensions: dict[str, str | None] = {}

    for node in _mapping_values(payload.get("semantic_models", {})):
        name = node["name"]
        default_agg_time_dimension = _nested_mapping_get(node, "defaults", "agg_time_dimension")
        semantic_models[name] = SemanticModelContract(
            name=name,
            model_name=_semantic_model_backing_model_name(node),
            agg_time_dimension=default_agg_time_dimension,
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
                    granularity=_nested_mapping_get(dimension, "type_params", "time_granularity")
                    or dimension.get("granularity"),
                )
                for dimension in node.get("dimensions", [])
            },
        )
        model_default_agg_time_dimensions[name] = default_agg_time_dimension
        measures_by_model[name] = {
            measure["name"]: measure
            for measure in node.get("measures", []) or []
            if isinstance(measure, dict) and "name" in measure
        }

    for node in _mapping_values(payload.get("metrics", {})):
        metric = _build_metric_contract_from_semantic_manifest(
            node,
            measures_by_model=measures_by_model,
            model_default_agg_time_dimensions=model_default_agg_time_dimensions,
        )
        metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)


def _build_contract_from_yaml_documents(documents: Iterable[tuple[str, str]]) -> SemanticContract:
    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}

    for source_file, content in documents:
        for payload in yaml.load_all(content, Loader=_LineLoader):
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
                    source=_source_for_key(model, "semantic_model", source_file, semantic_block),
                )

                for column in model.get("columns", []) or []:
                    if not isinstance(column, dict) or "name" not in column:
                        continue
                    _attach_column_semantics(contract, column, source_file)

                semantic_models[semantic_name] = contract

                for metric_payload in model.get("metrics", []) or []:
                    if not isinstance(metric_payload, dict):
                        continue
                    metric = _build_metric_contract(metric_payload, owner_model=semantic_name, source_file=source_file)
                    metrics[metric.name] = metric

            for metric_payload in payload.get("metrics", []) or []:
                if not isinstance(metric_payload, dict):
                    continue
                metric = _build_metric_contract(metric_payload, owner_model=None, source_file=source_file)
                metrics[metric.name] = metric

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)


def _attach_column_semantics(contract: SemanticModelContract, column: dict[str, Any], source_file: str) -> None:
    column_name = column["name"]
    column_expr = column.get("expr") or column_name

    entity_payload = column.get("entity")
    if isinstance(entity_payload, dict):
        entity_name = entity_payload.get("name") or column_name
        contract.entities[entity_name] = EntityContract(
            name=entity_name,
            type=entity_payload["type"],
            expr=entity_payload.get("expr") or column_expr,
            source=_source_for_key(column, "entity", source_file, entity_payload),
        )

    dimension_payload = column.get("dimension")
    if isinstance(dimension_payload, dict):
        dimension_name = dimension_payload.get("name") or column_name
        contract.dimensions[dimension_name] = DimensionContract(
            name=dimension_name,
            type=dimension_payload["type"],
            expr=dimension_payload.get("expr") or column_expr,
            granularity=column.get("granularity"),
            source=_source_for_key(column, "dimension", source_file, dimension_payload),
        )


def _build_metric_contract(payload: dict[str, Any], owner_model: str | None, source_file: str | None = None) -> MetricContract:
    return MetricContract(
        name=payload["name"],
        type=payload["type"],
        label=payload.get("label"),
        agg=payload.get("agg"),
        expr=_normalize_value(payload.get("expr")),
        filter=_normalize_filter_value(payload.get("filter")),
        agg_time_dimension=payload.get("agg_time_dimension"),
        numerator=_normalize_metric_ref(payload.get("numerator")),
        denominator=_normalize_metric_ref(payload.get("denominator")),
        input_metrics=_normalize_input_metrics(payload.get("input_metrics")),
        input_metric=_normalize_metric_ref(payload.get("input_metric")),
        window=_normalize_value(payload.get("window")),
        grain_to_date=_normalize_value(payload.get("grain_to_date")),
        period_agg=_normalize_value(payload.get("period_agg")),
        entity=_normalize_metric_ref(payload.get("entity")),
        calculation=_normalize_value(payload.get("calculation")),
        base_metric=_normalize_metric_ref(payload.get("base_metric")),
        conversion_metric=_normalize_metric_ref(payload.get("conversion_metric")),
        constant_properties=_normalize_value(payload.get("constant_properties")),
        non_additive_dimension=payload.get("non_additive_dimension"),
        owner_model=owner_model,
        source=_source_for(payload, source_file),
    )


def _build_metric_contract_from_semantic_manifest(
    payload: dict[str, Any],
    measures_by_model: dict[str, dict[str, dict[str, Any]]],
    model_default_agg_time_dimensions: dict[str, str | None],
) -> MetricContract:
    type_params = payload.get("type_params") or {}
    metric_aggregation_params = type_params.get("metric_aggregation_params") or {}
    cumulative_type_params = type_params.get("cumulative_type_params") or {}
    conversion_type_params = type_params.get("conversion_type_params") or {}
    metric_type = str(payload["type"])
    owner_model = metric_aggregation_params.get("semantic_model")
    measure_name = _normalize_metric_ref(type_params.get("measure"))
    measure_payload = None

    if metric_type == "simple":
        if not owner_model:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' is missing "
                "'type_params.metric_aggregation_params.semantic_model'"
            )
        if not measure_name:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' is missing 'type_params.measure'"
            )
        measure_payload = measures_by_model.get(owner_model, {}).get(measure_name)
        if measure_payload is None:
            raise ValueError(
                f"semantic_manifest.json simple metric '{payload['name']}' references measure "
                f"'{measure_name}' in semantic model '{owner_model}', but that measure was not found."
            )

    expr = _normalize_value(payload.get("expr"))
    if metric_type == "simple" and measure_payload is not None:
        expr = _normalize_value(measure_payload.get("expr") or measure_name)
    elif metric_type == "derived":
        expr = _normalize_value(type_params.get("expr"))

    agg = _normalize_value(metric_aggregation_params.get("agg"))
    if agg is None and measure_payload is not None:
        agg = _normalize_value(measure_payload.get("agg"))

    agg_time_dimension = metric_aggregation_params.get("agg_time_dimension")
    if agg_time_dimension is None and measure_payload is not None:
        agg_time_dimension = measure_payload.get("agg_time_dimension")
    if agg_time_dimension == model_default_agg_time_dimensions.get(owner_model):
        agg_time_dimension = None

    non_additive_dimension = metric_aggregation_params.get("non_additive_dimension")
    if non_additive_dimension is None and measure_payload is not None:
        non_additive_dimension = measure_payload.get("non_additive_dimension")

    return MetricContract(
        name=payload["name"],
        type=metric_type,
        label=payload.get("label"),
        agg=agg,
        expr=expr,
        filter=_normalize_filter_value(payload.get("filter")),
        agg_time_dimension=agg_time_dimension,
        numerator=_normalize_metric_ref(type_params.get("numerator")),
        denominator=_normalize_metric_ref(type_params.get("denominator")),
        input_metrics=_normalize_input_metrics(type_params.get("metrics") or payload.get("input_metrics")),
        input_metric=_normalize_metric_ref(type_params.get("input_metric") or type_params.get("measure") or payload.get("input_metric"))
        if metric_type == "cumulative"
        else None,
        window=_normalize_value(cumulative_type_params.get("window") or type_params.get("window") or payload.get("window"))
        if metric_type == "cumulative"
        else None,
        grain_to_date=_normalize_value(
            cumulative_type_params.get("grain_to_date") or type_params.get("grain_to_date") or payload.get("grain_to_date")
        )
        if metric_type == "cumulative"
        else None,
        period_agg=_normalize_value(
            cumulative_type_params.get("period_agg") or type_params.get("period_agg") or payload.get("period_agg")
        )
        if metric_type == "cumulative"
        else None,
        entity=_normalize_metric_ref(conversion_type_params.get("entity") or type_params.get("entity") or payload.get("entity"))
        if metric_type == "conversion"
        else None,
        calculation=_normalize_value(
            conversion_type_params.get("calculation") or type_params.get("calculation") or payload.get("calculation")
        )
        if metric_type == "conversion"
        else None,
        base_metric=_normalize_metric_ref(
            conversion_type_params.get("base_metric")
            or conversion_type_params.get("base_measure")
            or type_params.get("base_metric")
            or payload.get("base_metric")
        )
        if metric_type == "conversion"
        else None,
        conversion_metric=_normalize_metric_ref(
            conversion_type_params.get("conversion_metric")
            or conversion_type_params.get("conversion_measure")
            or type_params.get("conversion_metric")
            or payload.get("conversion_metric")
        )
        if metric_type == "conversion"
        else None,
        constant_properties=_normalize_value(
            conversion_type_params.get("constant_properties")
            or type_params.get("constant_properties")
            or payload.get("constant_properties")
        )
        if metric_type == "conversion"
        else None,
        non_additive_dimension=non_additive_dimension,
        owner_model=owner_model,
    )


def _normalize_metric_ref(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = _without_loader_metadata(value)
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
        if isinstance(item, dict):
            item = _without_loader_metadata(item)
        if isinstance(item, dict) and "name" in item and set(item.keys()) == {"name"}:
            normalized.append(str(item["name"]))
        else:
            normalized.append(json.dumps(item, sort_keys=True))
    return normalized


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(_without_loader_metadata(value), sort_keys=True)
    return str(value)


def _normalize_filter_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = _without_loader_metadata(value)
        where_sql_template = value.get("where_sql_template")
        if isinstance(where_sql_template, str):
            return where_sql_template
        where_filters = value.get("where_filters")
        if isinstance(where_filters, list):
            parts = [
                item["where_sql_template"]
                for item in where_filters
                if isinstance(item, dict) and isinstance(item.get("where_sql_template"), str)
            ]
            if parts:
                return " AND ".join(parts)
    return _normalize_value(value)


def _mapping_values(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _looks_like_plain_dbt_manifest(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    schema_version = metadata.get("dbt_schema_version") if isinstance(metadata, dict) else None
    return ("nodes" in payload or "parent_map" in payload) and (
        isinstance(schema_version, str) and "/manifest/" in schema_version or "semantic_models" not in payload
    )


def _looks_like_semantic_manifest_payload(payload: dict[str, Any]) -> bool:
    semantic_models = _mapping_values(payload.get("semantic_models"))
    if not semantic_models:
        return False
    first_model = semantic_models[0]
    return any(key in first_model for key in ("node_relation", "defaults", "measures"))


def _semantic_model_backing_model_name(node: dict[str, Any]) -> str:
    node_relation = node.get("node_relation")
    if isinstance(node_relation, dict):
        for key in ("alias", "relation_name"):
            value = node_relation.get(key)
            if value:
                return str(value)
    return str(node.get("model_name") or node["name"])


def _nested_mapping_get(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _source_for(value: Any, source_file: str | None) -> SourceLocation | None:
    if source_file is None or not isinstance(value, dict) or _SOURCE_LINE_KEY not in value:
        return None
    return SourceLocation(
        file=source_file,
        line=int(value[_SOURCE_LINE_KEY]),
        end_line=int(value.get(_SOURCE_END_LINE_KEY) or value[_SOURCE_LINE_KEY]),
    )


def _without_loader_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_loader_metadata(item)
            for key, item in value.items()
            if key not in {_SOURCE_LINE_KEY, _SOURCE_END_LINE_KEY, _SOURCE_KEY_LINES_KEY}
        }
    if isinstance(value, list):
        return [_without_loader_metadata(item) for item in value]
    return value


def _source_for_key(
    container: dict[str, Any],
    key: str,
    source_file: str | None,
    fallback_value: dict[str, Any] | None = None,
) -> SourceLocation | None:
    if source_file is None or not isinstance(container, dict):
        return None
    key_lines = container.get(_SOURCE_KEY_LINES_KEY)
    if isinstance(key_lines, dict) and key in key_lines:
        end_line = None
        if isinstance(fallback_value, dict):
            end_line = int(fallback_value.get(_SOURCE_END_LINE_KEY) or key_lines[key])
        return SourceLocation(file=source_file, line=int(key_lines[key]), end_line=end_line)
    return _source_for(fallback_value or container.get(key), source_file)
