from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from dbt_semguard.models import ChangeRecord, MetricContract, SemanticContract


@dataclass(frozen=True)
class FieldComparator:
    field_name: str
    code: str


SEVERITY_BY_CODE = {
    "semantic_model.added": "risky",
    "semantic_model.removed": "breaking",
    "semantic_model.model_changed": "breaking",
    "semantic_model.agg_time_dimension_changed": "risky",
    "entity.added": "risky",
    "entity.removed": "breaking",
    "entity.type_changed": "breaking",
    "entity.expr_changed": "breaking",
    "dimension.added": "risky",
    "dimension.removed": "breaking",
    "dimension.type_changed": "breaking",
    "dimension.expr_changed": "breaking",
    "dimension.granularity_changed": "risky",
    "metric.added": "risky",
    "metric.removed": "breaking",
    "metric.type_changed": "breaking",
    "metric.owner_model_changed": "breaking",
    "metric.label_changed": "risky",
    "metric.filter_changed": "risky",
    "metric.agg_time_dimension_changed": "risky",
    "metric.simple.agg_changed": "breaking",
    "metric.simple.expr_changed": "breaking",
    "metric.simple.non_additive_dimension_changed": "breaking",
    "metric.ratio.numerator_changed": "breaking",
    "metric.ratio.denominator_changed": "breaking",
    "metric.derived.inputs_changed": "breaking",
    "metric.derived.expr_changed": "breaking",
}

SEMANTIC_MODEL_COMPARATORS = (
    FieldComparator("model_name", "semantic_model.model_changed"),
    FieldComparator("agg_time_dimension", "semantic_model.agg_time_dimension_changed"),
)

ENTITY_COMPARATORS = (
    FieldComparator("type", "entity.type_changed"),
    FieldComparator("expr", "entity.expr_changed"),
)

DIMENSION_COMPARATORS = (
    FieldComparator("type", "dimension.type_changed"),
    FieldComparator("expr", "dimension.expr_changed"),
    FieldComparator("granularity", "dimension.granularity_changed"),
)

METRIC_COMMON_COMPARATORS = (
    FieldComparator("owner_model", "metric.owner_model_changed"),
    FieldComparator("label", "metric.label_changed"),
    FieldComparator("filter", "metric.filter_changed"),
    FieldComparator("agg_time_dimension", "metric.agg_time_dimension_changed"),
)

METRIC_TYPE_COMPARATORS = {
    "simple": (
        FieldComparator("agg", "metric.simple.agg_changed"),
        FieldComparator("expr", "metric.simple.expr_changed"),
        FieldComparator("non_additive_dimension", "metric.simple.non_additive_dimension_changed"),
    ),
    "ratio": (
        FieldComparator("numerator", "metric.ratio.numerator_changed"),
        FieldComparator("denominator", "metric.ratio.denominator_changed"),
    ),
    "derived": (
        FieldComparator("expr", "metric.derived.expr_changed"),
        FieldComparator("input_metrics", "metric.derived.inputs_changed"),
    ),
}

FIELD_DIFF_POLICY = {
    "SemanticContract": {
        "semantic_models": None,
        "metrics": None,
    },
    "SemanticModelContract": {
        "name": False,
        "model_name": "semantic_model.model_changed",
        "agg_time_dimension": "semantic_model.agg_time_dimension_changed",
        "entities": None,
        "dimensions": None,
        "source": False,
    },
    "EntityContract": {
        "name": False,
        "type": "entity.type_changed",
        "expr": "entity.expr_changed",
        "source": False,
    },
    "DimensionContract": {
        "name": False,
        "type": "dimension.type_changed",
        "expr": "dimension.expr_changed",
        "granularity": "dimension.granularity_changed",
        "source": False,
    },
    "MetricContract": {
        "name": False,
        "metric_type": "metric.type_changed",
        "label": "metric.label_changed",
        "agg": {"simple": "metric.simple.agg_changed"},
        "expr": {
            "simple": "metric.simple.expr_changed",
            "derived": "metric.derived.expr_changed",
        },
        "filter": "metric.filter_changed",
        "agg_time_dimension": "metric.agg_time_dimension_changed",
        "numerator": {"ratio": "metric.ratio.numerator_changed"},
        "denominator": {"ratio": "metric.ratio.denominator_changed"},
        "input_metrics": {"derived": "metric.derived.inputs_changed"},
        "non_additive_dimension": {"simple": "metric.simple.non_additive_dimension_changed"},
        "owner_model": "metric.owner_model_changed",
        "source": False,
    },
}


def diff_contracts(base: SemanticContract, head: SemanticContract) -> list[ChangeRecord]:
    changes: list[ChangeRecord] = []

    for name in sorted(set(base.semantic_models) | set(head.semantic_models)):
        base_model = base.semantic_models.get(name)
        head_model = head.semantic_models.get(name)
        path = f"semantic_models.{name}"

        if base_model is None and head_model is not None:
            changes.append(_change("semantic_model.added", path, None, head_model.model_dump(mode="json"), head_model.source))
            continue
        if base_model is not None and head_model is None:
            changes.append(_change("semantic_model.removed", path, base_model.model_dump(mode="json"), None, base_model.source))
            continue
        assert base_model is not None and head_model is not None

        _diff_fields(path, base_model, head_model, SEMANTIC_MODEL_COMPARATORS, changes)
        _diff_nested_contracts(
            path=f"{path}.entities",
            base_items=base_model.entities,
            head_items=head_model.entities,
            added_code="entity.added",
            removed_code="entity.removed",
            comparators=ENTITY_COMPARATORS,
            changes=changes,
        )
        _diff_nested_contracts(
            path=f"{path}.dimensions",
            base_items=base_model.dimensions,
            head_items=head_model.dimensions,
            added_code="dimension.added",
            removed_code="dimension.removed",
            comparators=DIMENSION_COMPARATORS,
            changes=changes,
        )

    for metric_name in sorted(set(base.metrics) | set(head.metrics)):
        base_metric = base.metrics.get(metric_name)
        head_metric = head.metrics.get(metric_name)
        path = f"metrics.{metric_name}"

        if base_metric is None and head_metric is not None:
            changes.append(_change("metric.added", path, None, head_metric.model_dump(mode="json"), head_metric.source))
            continue
        if base_metric is not None and head_metric is None:
            changes.append(_change("metric.removed", path, base_metric.model_dump(mode="json"), None, base_metric.source))
            continue
        assert base_metric is not None and head_metric is not None

        _diff_metric(path, base_metric, head_metric, changes)

    return changes


def _diff_metric(path: str, base_metric: MetricContract, head_metric: MetricContract, changes: list[ChangeRecord]) -> None:
    if base_metric.metric_type != head_metric.metric_type:
        changes.append(
            _change("metric.type_changed", path, base_metric.metric_type, head_metric.metric_type, head_metric.source or base_metric.source)
        )
        return

    _diff_fields(path, base_metric, head_metric, METRIC_COMMON_COMPARATORS, changes)
    _diff_fields(path, base_metric, head_metric, METRIC_TYPE_COMPARATORS.get(base_metric.metric_type, ()), changes)


def _diff_nested_contracts(
    *,
    path: str,
    base_items: dict[str, Any],
    head_items: dict[str, Any],
    added_code: str,
    removed_code: str,
    comparators: tuple[FieldComparator, ...],
    changes: list[ChangeRecord],
) -> None:
    for item_name in sorted(set(base_items) | set(head_items)):
        base_item = base_items.get(item_name)
        head_item = head_items.get(item_name)
        item_path = f"{path}.{item_name}"

        if base_item is None and head_item is not None:
            changes.append(_change(added_code, item_path, None, head_item.model_dump(mode="json"), head_item.source))
            continue
        if base_item is not None and head_item is None:
            changes.append(_change(removed_code, item_path, base_item.model_dump(mode="json"), None, base_item.source))
            continue
        assert base_item is not None and head_item is not None

        _diff_fields(item_path, base_item, head_item, comparators, changes)


def _diff_fields(path: str, base_obj: Any, head_obj: Any, comparators: tuple[FieldComparator, ...], changes: list[ChangeRecord]) -> None:
    for comparator in comparators:
        before = getattr(base_obj, comparator.field_name)
        after = getattr(head_obj, comparator.field_name)
        if before != after:
            changes.append(_change(comparator.code, path, before, after, head_obj.source or base_obj.source))


def _change(code: str, path: str, before: object, after: object, source=None) -> ChangeRecord:
    return ChangeRecord(
        code=code,
        severity=SEVERITY_BY_CODE[code],
        path=path,
        before=before,
        after=after,
        message=_describe_change(code, path, before, after),
        source=source,
    )


def describe_path_title(path: str) -> str:
    parts = path.split(".")
    if not parts:
        return path
    if parts[0] == "metrics" and len(parts) >= 2:
        return f"Metric `{parts[1]}`"
    if parts[0] == "semantic_models" and len(parts) == 2:
        return f"Semantic model `{parts[1]}`"
    if parts[0] == "semantic_models" and len(parts) >= 4 and parts[2] == "entities":
        return f"Entity `{parts[3]}` in semantic model `{parts[1]}`"
    if parts[0] == "semantic_models" and len(parts) >= 4 and parts[2] == "dimensions":
        return f"Dimension `{parts[3]}` in semantic model `{parts[1]}`"
    return f"`{parts[-1]}`"


def _describe_change(code: str, path: str, before: object, after: object) -> str:
    subject = _subject_for_change(code, path)
    messages = {
        "semantic_model.added": f"{subject} was added.",
        "semantic_model.removed": f"{subject} was removed.",
        "semantic_model.model_changed": f"{subject} changed backing model from `{before}` to `{after}`.",
        "semantic_model.agg_time_dimension_changed": (
            f"{subject} changed default aggregation time dimension from `{before}` to `{after}`."
        ),
        "entity.added": f"{subject} was added.",
        "entity.removed": f"{subject} was removed.",
        "entity.type_changed": f"{subject} changed type from `{before}` to `{after}`.",
        "entity.expr_changed": f"{subject} changed expression from `{before}` to `{after}`.",
        "dimension.added": f"{subject} was added.",
        "dimension.removed": f"{subject} was removed.",
        "dimension.type_changed": f"{subject} changed type from `{before}` to `{after}`.",
        "dimension.expr_changed": f"{subject} changed expression from `{before}` to `{after}`.",
        "dimension.granularity_changed": f"{subject} changed granularity from `{before}` to `{after}`.",
        "metric.added": f"{subject} was added.",
        "metric.removed": f"{subject} was removed.",
        "metric.type_changed": f"{subject} changed type from `{before}` to `{after}`.",
        "metric.owner_model_changed": f"{subject} changed owning semantic model from `{before}` to `{after}`.",
        "metric.label_changed": f"{subject} changed label from `{before}` to `{after}`.",
        "metric.filter_changed": f"{subject} changed filter from `{before}` to `{after}`.",
        "metric.agg_time_dimension_changed": (
            f"{subject} changed aggregation time dimension from `{before}` to `{after}`."
        ),
        "metric.simple.agg_changed": f"{subject} changed aggregation from `{before}` to `{after}`.",
        "metric.simple.expr_changed": f"{subject} changed expression from `{before}` to `{after}`.",
        "metric.simple.non_additive_dimension_changed": (
            f"{subject} changed non-additive dimension from `{before}` to `{after}`."
        ),
        "metric.ratio.numerator_changed": f"{subject} changed numerator from `{before}` to `{after}`.",
        "metric.ratio.denominator_changed": f"{subject} changed denominator from `{before}` to `{after}`.",
        "metric.derived.inputs_changed": f"{subject} changed derived inputs from `{before}` to `{after}`.",
        "metric.derived.expr_changed": f"{subject} changed derived expression from `{before}` to `{after}`.",
    }
    return messages[code]


def _subject_for_change(code: str, path: str) -> str:
    subject = describe_path_title(path)
    prefixes = OrderedDict(
        [
            ("metric.simple.", "Simple metric"),
            ("metric.ratio.", "Ratio metric"),
            ("metric.derived.", "Derived metric"),
        ]
    )
    for prefix, replacement in prefixes.items():
        if code.startswith(prefix):
            return subject.replace("Metric", replacement, 1)
    return subject
