from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from dbt_semguard.git_utils import load_yaml_documents_from_git_ref
from dbt_semguard.models import (
    DimensionContract,
    EntityContract,
    MeasureContract,
    MetricContract,
    SemanticContract,
    SemanticModelContract,
    SourceLocation,
)
from dbt_semguard.normalization import (
    _nested_mapping_get,
    _normalize_filter_value,
    _normalize_input_metrics,
    _normalize_metric_ref,
    _normalize_value,
)

_SOURCE_LINE_KEY = "__semguard_source_line__"
_SOURCE_END_LINE_KEY = "__semguard_source_end_line__"
_SOURCE_KEY_LINES_KEY = "__semguard_source_key_lines__"
_DEFAULT_INCLUDE_PATTERNS = (
    "models/**/*.yml",
    "models/**/*.yaml",
    "metrics/**/*.yml",
    "metrics/**/*.yaml",
    "semantic_models/**/*.yml",
    "semantic_models/**/*.yaml",
)
_DEFAULT_EXCLUDE_PATTERNS = (
    "target/**",
    "dbt_packages/**",
    ".venv/**",
    "venv/**",
    ".github/**",
)

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
    include_patterns, exclude_patterns = _load_yaml_discovery_filters(root)
    file_filter = _build_file_filter(include_patterns, exclude_patterns)
    documents = [
        (path.relative_to(root).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".yml", ".yaml"} and file_filter(path.relative_to(root).as_posix())
    ]
    return _build_contract_from_yaml_documents(documents)

def extract_contract_from_git_ref(project_dir: str | Path, git_ref: str) -> SemanticContract:
    root = Path(project_dir)
    include_patterns, exclude_patterns = _load_yaml_discovery_filters_from_git_ref(root, git_ref)
    return _build_contract_from_yaml_documents(
        load_yaml_documents_from_git_ref(
            root,
            git_ref,
            file_filter=_build_file_filter(include_patterns, exclude_patterns),
        )
    )

def _build_contract_from_yaml_documents(documents: Iterable[tuple[str, str]]) -> SemanticContract:
    semantic_models: dict[str, SemanticModelContract] = {}
    metrics: dict[str, MetricContract] = {}

    for source_file, content in documents:
        try:
            payloads = yaml.load_all(content, Loader=_LineLoader)
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                legacy_measures_by_model: dict[str, dict[str, dict[str, Any]]] = {}
                legacy_model_default_agg_time_dimensions: dict[str, str | None] = {}
                for model in payload.get("models", []) or []:
                    if not isinstance(model, dict):
                        continue
                    semantic_block = model.get("semantic_model")
                    if semantic_block is None:
                        continue
                    if not isinstance(semantic_block, dict):
                        raise _yaml_validation_error(
                            source_file,
                            "Invalid semantic model definition: 'semantic_model' must be a mapping.",
                            payload=model,
                            key="semantic_model",
                        )
                    if semantic_block.get("enabled", True) is False:
                        continue
                    model_name = _required_value(
                        model,
                        key="name",
                        source_file=source_file,
                        kind="model",
                        fallback_payload=semantic_block,
                    )
                    semantic_name = semantic_block.get("name") or model_name
                    contract = SemanticModelContract(
                        name=str(semantic_name),
                        model_name=str(model_name),
                        agg_time_dimension=model.get("agg_time_dimension"),
                        source=_source_for_key(model, "semantic_model", source_file, semantic_block),
                    )

                    for column in model.get("columns", []) or []:
                        if not isinstance(column, dict) or "name" not in column:
                            continue
                        _attach_column_semantics(contract, column, source_file)

                    semantic_models[contract.name] = contract

                    for metric_payload in model.get("metrics", []) or []:
                        if not isinstance(metric_payload, dict):
                            continue
                        metric = _build_metric_contract(metric_payload, owner_model=contract.name, source_file=source_file)
                        metrics[metric.name] = metric
                for semantic_model_payload in payload.get("semantic_models", []) or []:
                    if not isinstance(semantic_model_payload, dict):
                        continue
                    contract = _build_legacy_yaml_semantic_model_contract(semantic_model_payload, source_file)
                    semantic_models[contract.name] = contract
                    legacy_model_default_agg_time_dimensions[contract.name] = contract.agg_time_dimension
                    legacy_measures_by_model[contract.name] = {
                        measure["name"]: measure
                        for measure in semantic_model_payload.get("measures", []) or []
                        if isinstance(measure, dict) and "name" in measure
                    }
                for metric_payload in payload.get("metrics", []) or []:
                    if not isinstance(metric_payload, dict):
                        continue
                    if payload.get("semantic_models") or metric_payload.get("type_params"):
                        metric = _build_metric_contract_from_semantic_manifest(
                            metric_payload,
                            measures_by_model=legacy_measures_by_model,
                            model_default_agg_time_dimensions=legacy_model_default_agg_time_dimensions,
                            source_file=source_file,
                        )
                    else:
                        metric = _build_metric_contract(metric_payload, owner_model=None, source_file=source_file)
                    metrics[metric.name] = metric

        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            line_suffix = f":{mark.line + 1}" if mark is not None else ""
            message = getattr(exc, "problem", None) or str(exc)
            raise ValueError(f"Malformed YAML in '{source_file}{line_suffix}': {message}") from exc

    return SemanticContract(semantic_models=semantic_models, metrics=metrics)

def _attach_column_semantics(contract: SemanticModelContract, column: dict[str, Any], source_file: str) -> None:
    column_name = column["name"]
    column_expr = column.get("expr") or column_name

    entity_payload = column.get("entity")
    if isinstance(entity_payload, dict):
        entity_name = entity_payload.get("name") or column_name
        entity_type = _required_value(
            entity_payload,
            key="type",
            source_file=source_file,
            kind=f"entity '{entity_name}'",
            fallback_payload=column,
            fallback_key="entity",
        )
        contract.entities[entity_name] = EntityContract(
            name=entity_name,
            type=str(entity_type),
            expr=entity_payload.get("expr") or column_expr,
            source=_source_for_key(column, "entity", source_file, entity_payload),
        )

    dimension_payload = column.get("dimension")
    if isinstance(dimension_payload, dict):
        dimension_name = dimension_payload.get("name") or column_name
        dimension_type = _required_value(
            dimension_payload,
            key="type",
            source_file=source_file,
            kind=f"dimension '{dimension_name}'",
            fallback_payload=column,
            fallback_key="dimension",
        )
        contract.dimensions[dimension_name] = DimensionContract(
            name=dimension_name,
            type=str(dimension_type),
            expr=dimension_payload.get("expr") or column_expr,
            granularity=column.get("granularity"),
            source=_source_for_key(column, "dimension", source_file, dimension_payload),
        )

def _build_legacy_yaml_semantic_model_contract(payload: dict[str, Any], source_file: str) -> SemanticModelContract:
    semantic_name = str(
        _required_value(
            payload,
            key="name",
            source_file=source_file,
            kind="semantic model",
        )
    )
    model_reference = payload.get("model_name") or payload.get("model") or semantic_name
    contract = SemanticModelContract(
        name=semantic_name,
        model_name=_normalize_legacy_model_reference(model_reference),
        agg_time_dimension=_nested_mapping_get(payload, "defaults", "agg_time_dimension"),
        source=_source_for(payload, source_file),
    )

    for entity_payload in payload.get("entities", []) or []:
        if not isinstance(entity_payload, dict):
            continue
        entity_name = str(
            _required_value(
                entity_payload,
                key="name",
                source_file=source_file,
                kind="entity",
            )
        )
        entity_type = _required_value(
            entity_payload,
            key="type",
            source_file=source_file,
            kind=f"entity '{entity_name}'",
        )
        contract.entities[entity_name] = EntityContract(
            name=entity_name,
            type=str(entity_type),
            expr=str(entity_payload.get("expr") or entity_name),
            source=_source_for(entity_payload, source_file),
        )

    for dimension_payload in payload.get("dimensions", []) or []:
        if not isinstance(dimension_payload, dict):
            continue
        dimension_name = str(
            _required_value(
                dimension_payload,
                key="name",
                source_file=source_file,
                kind="dimension",
            )
        )
        dimension_type = _required_value(
            dimension_payload,
            key="type",
            source_file=source_file,
            kind=f"dimension '{dimension_name}'",
        )
        contract.dimensions[dimension_name] = DimensionContract(
            name=dimension_name,
            type=str(dimension_type),
            expr=str(dimension_payload.get("expr") or dimension_name),
            granularity=_nested_mapping_get(dimension_payload, "type_params", "time_granularity")
            or dimension_payload.get("granularity"),
            source=_source_for(dimension_payload, source_file),
        )

    for measure_payload in payload.get("measures", []) or []:
        if not isinstance(measure_payload, dict):
            continue
        measure_name = str(
            _required_value(
                measure_payload,
                key="name",
                source_file=source_file,
                kind="measure",
            )
        )
        contract.measures[measure_name] = MeasureContract(
            name=measure_name,
            agg=measure_payload.get("agg"),
            expr=str(measure_payload.get("expr") or measure_name),
            agg_time_dimension=measure_payload.get("agg_time_dimension"),
            non_additive_dimension=measure_payload.get("non_additive_dimension"),
            source=_source_for(measure_payload, source_file),
        )

    return contract

def _build_metric_contract(payload: dict[str, Any], owner_model: str | None, source_file: str | None = None) -> MetricContract:
    metric_name = _required_value(
        payload,
        key="name",
        source_file=source_file,
        kind="metric",
    )
    metric_type = _required_value(
        payload,
        key="type",
        source_file=source_file,
        kind=f"metric '{metric_name}'",
    )
    return MetricContract(
        name=str(metric_name),
        metric_type=str(metric_type),
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

def _required_value(
    payload: dict[str, Any],
    key: str,
    source_file: str | None,
    kind: str,
    fallback_payload: dict[str, Any] | None = None,
    fallback_key: str | None = None,
) -> Any:
    value = payload.get(key)
    if value is not None:
        return value
    raise _yaml_validation_error(
        source_file,
        f"Invalid {kind} definition: missing required '{key}'.",
        payload=payload if fallback_payload is None else fallback_payload,
        key=fallback_key or key,
    )

def _yaml_validation_error(
    source_file: str | None,
    message: str,
    payload: dict[str, Any] | None = None,
    key: str | None = None,
) -> ValueError:
    location = _error_location(source_file, payload=payload, key=key)
    if location:
        return ValueError(f"{message} ({location})")
    return ValueError(message)

def _error_location(source_file: str | None, payload: dict[str, Any] | None, key: str | None) -> str:
    if source_file is None:
        return ""
    line = None
    if isinstance(payload, dict):
        if key is not None:
            key_lines = payload.get(_SOURCE_KEY_LINES_KEY)
            if isinstance(key_lines, dict):
                line_value = key_lines.get(key)
                if isinstance(line_value, int):
                    line = line_value
        if line is None:
            line_value = payload.get(_SOURCE_LINE_KEY)
            if isinstance(line_value, int):
                line = line_value
    return f"{source_file}:{line}" if line is not None else source_file

def _load_yaml_discovery_filters(project_dir: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    config_path = project_dir / ".semguard.yml"
    if not config_path.exists():
        return _DEFAULT_INCLUDE_PATTERNS, _DEFAULT_EXCLUDE_PATTERNS

    return _parse_yaml_discovery_filters(
        config_path.read_text(encoding="utf-8"),
        source=str(config_path),
    )

def _load_yaml_discovery_filters_from_git_ref(project_dir: Path, git_ref: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    config_documents = load_yaml_documents_from_git_ref(
        project_dir,
        git_ref,
        file_filter=lambda path: path == ".semguard.yml",
    )
    if not config_documents:
        return _DEFAULT_INCLUDE_PATTERNS, _DEFAULT_EXCLUDE_PATTERNS

    source_path, content = config_documents[0]
    return _parse_yaml_discovery_filters(content, source=f"{source_path}@{git_ref}")

def _parse_yaml_discovery_filters(content: str, source: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    includes = _DEFAULT_INCLUDE_PATTERNS
    excludes = _DEFAULT_EXCLUDE_PATTERNS

    try:
        config_data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line_suffix = f":{mark.line + 1}" if mark is not None else ""
        message = getattr(exc, "problem", None) or str(exc)
        raise ValueError(f"Invalid .semguard.yml at '{source}{line_suffix}': {message}") from exc
    if config_data is None:
        return includes, excludes
    if not isinstance(config_data, dict):
        raise ValueError(f"Invalid .semguard.yml: expected a mapping at '{source}'.")

    includes = _coerce_pattern_list(config_data.get("include"), default=_DEFAULT_INCLUDE_PATTERNS, key="include")
    excludes = _coerce_pattern_list(config_data.get("exclude"), default=_DEFAULT_EXCLUDE_PATTERNS, key="exclude")
    return includes, excludes

def _coerce_pattern_list(value: Any, default: tuple[str, ...], key: str) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Invalid .semguard.yml: '{key}' must be a list of glob patterns.")
    return tuple(item.strip() for item in value if item.strip())

def _build_file_filter(include_patterns: tuple[str, ...], exclude_patterns: tuple[str, ...]) -> Callable[[str], bool]:
    include_regexes = [_glob_pattern_to_regex(pattern) for pattern in include_patterns]
    exclude_regexes = [_glob_pattern_to_regex(pattern) for pattern in exclude_patterns]

    def _matches(path: str) -> bool:
        normalized = path.strip("/")
        if any(pattern.fullmatch(normalized) for pattern in exclude_regexes):
            return False
        return any(pattern.fullmatch(normalized) for pattern in include_regexes)

    return _matches

def _glob_pattern_to_regex(pattern: str) -> re.Pattern[str]:
    normalized = pattern.strip()
    parts: list[str] = ["^"]
    i = 0
    while i < len(normalized):
        char = normalized[i]
        if char == "*":
            if i + 1 < len(normalized) and normalized[i + 1] == "*":
                i += 1
                if i + 1 < len(normalized) and normalized[i + 1] == "/":
                    i += 1
                    parts.append("(?:.*/)?")
                else:
                    parts.append(".*")
            else:
                parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(char))
        i += 1
    parts.append("$")
    return re.compile("".join(parts))

def _normalize_legacy_model_reference(value: Any) -> str:
    text = str(value).strip()
    quoted_args = re.findall(r"""['"]([^'"]+)['"]""", text)
    if text.startswith("ref(") and quoted_args:
        return quoted_args[-1]
    return text

def _source_for(value: Any, source_file: str | None) -> SourceLocation | None:
    if source_file is None or not isinstance(value, dict) or _SOURCE_LINE_KEY not in value:
        return None
    return SourceLocation(
        file=source_file,
        line=int(value[_SOURCE_LINE_KEY]),
        end_line=int(value.get(_SOURCE_END_LINE_KEY) or value[_SOURCE_LINE_KEY]),
    )

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