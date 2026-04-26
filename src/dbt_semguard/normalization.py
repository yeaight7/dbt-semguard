from __future__ import annotations

import json
import re
from typing import Any

def _normalize_metric_ref(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = _without_loader_metadata(value)
        for key in ("name", "measure", "metric"):
            if key in value:
                return str(value[key])
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
    raw_str = None
    if isinstance(value, str):
        raw_str = value
    elif isinstance(value, dict):
        value = _without_loader_metadata(value)
        where_sql_template = value.get("where_sql_template")
        if isinstance(where_sql_template, str):
            raw_str = where_sql_template
        else:
            where_filters = value.get("where_filters")
            if isinstance(where_filters, list):
                parts = [
                    item["where_sql_template"]
                    for item in where_filters
                    if isinstance(item, dict) and isinstance(item.get("where_sql_template"), str)
                ]
                if parts:
                    raw_str = " AND ".join(parts)
                    
    if raw_str is None:
        raw_str = _normalize_value(value)
        
    if raw_str is None:
        return None
        
    normalized = _collapse_unquoted_whitespace(raw_str)
    return _strip_unquoted_operator_spacing(normalized)

def _collapse_unquoted_whitespace(value: str) -> str:
    result: list[str] = []
    quote: str | None = None
    pending_space = False
    index = 0
    text = value.strip()

    while index < len(text):
        char = text[index]
        if quote:
            result.append(char)
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    result.append(text[index + 1])
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            if pending_space and result:
                result.append(" ")
            pending_space = False
            quote = char
            result.append(char)
        elif char.isspace():
            pending_space = True
        else:
            if pending_space and result:
                result.append(" ")
            pending_space = False
            result.append(char)
        index += 1

    return "".join(result).strip()

def _strip_unquoted_operator_spacing(value: str) -> str:
    result: list[str] = []
    quote: str | None = None
    operators = (">=", "<=", "!=", "<>", "=", ">", "<")
    index = 0

    while index < len(value):
        char = value[index]
        if quote:
            result.append(char)
            if char == quote:
                if index + 1 < len(value) and value[index + 1] == quote:
                    result.append(value[index + 1])
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
            result.append(char)
            index += 1
            continue

        operator = next((candidate for candidate in operators if value.startswith(candidate, index)), None)
        if operator is not None:
            while result and result[-1] == " ":
                result.pop()
            result.append(operator)
            index += len(operator)
            while index < len(value) and value[index] == " ":
                index += 1
            continue

        result.append(char)
        index += 1

    return "".join(result).strip()

def _mapping_values(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []

def _nested_mapping_get(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

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

normalize_metric_ref = _normalize_metric_ref
normalize_input_metrics = _normalize_input_metrics
normalize_value = _normalize_value
normalize_filter_value = _normalize_filter_value
mapping_values = _mapping_values
nested_mapping_get = _nested_mapping_get
without_loader_metadata = _without_loader_metadata
