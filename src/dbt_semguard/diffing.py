from __future__ import annotations

from dbt_semguard.models import ChangeRecord, MetricContract, SemanticContract


SEVERITY_BY_CODE = {
    "semantic_model.added": "risky",
    "semantic_model.removed": "breaking",
    "semantic_model.model_changed": "breaking",
    "semantic_model.agg_time_dimension_changed": "risky",
    "entity.added": "risky",
    "entity.removed": "breaking",
    "entity.type_changed": "breaking",
    "dimension.added": "risky",
    "dimension.removed": "breaking",
    "dimension.type_changed": "breaking",
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


def diff_contracts(base: SemanticContract, head: SemanticContract) -> list[ChangeRecord]:
    changes: list[ChangeRecord] = []

    for name in sorted(set(base.semantic_models) | set(head.semantic_models)):
        base_model = base.semantic_models.get(name)
        head_model = head.semantic_models.get(name)
        path = f"semantic_models.{name}"

        if base_model is None and head_model is not None:
            changes.append(_change("semantic_model.added", path, None, head_model.model_dump(mode="json")))
            continue
        if base_model is not None and head_model is None:
            changes.append(_change("semantic_model.removed", path, base_model.model_dump(mode="json"), None))
            continue
        assert base_model is not None and head_model is not None

        if base_model.model_name != head_model.model_name:
            changes.append(_change("semantic_model.model_changed", path, base_model.model_name, head_model.model_name))
        if base_model.agg_time_dimension != head_model.agg_time_dimension:
            changes.append(
                _change(
                    "semantic_model.agg_time_dimension_changed",
                    path,
                    base_model.agg_time_dimension,
                    head_model.agg_time_dimension,
                )
            )

        for entity_name in sorted(set(base_model.entities) | set(head_model.entities)):
            base_entity = base_model.entities.get(entity_name)
            head_entity = head_model.entities.get(entity_name)
            entity_path = f"{path}.entities.{entity_name}"
            if base_entity is None and head_entity is not None:
                changes.append(_change("entity.added", entity_path, None, head_entity.model_dump(mode="json")))
            elif base_entity is not None and head_entity is None:
                changes.append(_change("entity.removed", entity_path, base_entity.model_dump(mode="json"), None))
            elif base_entity is not None and head_entity is not None and base_entity.type != head_entity.type:
                changes.append(_change("entity.type_changed", entity_path, base_entity.type, head_entity.type))

        for dimension_name in sorted(set(base_model.dimensions) | set(head_model.dimensions)):
            base_dimension = base_model.dimensions.get(dimension_name)
            head_dimension = head_model.dimensions.get(dimension_name)
            dimension_path = f"{path}.dimensions.{dimension_name}"
            if base_dimension is None and head_dimension is not None:
                changes.append(_change("dimension.added", dimension_path, None, head_dimension.model_dump(mode="json")))
            elif base_dimension is not None and head_dimension is None:
                changes.append(_change("dimension.removed", dimension_path, base_dimension.model_dump(mode="json"), None))
            elif base_dimension is not None and head_dimension is not None:
                if base_dimension.type != head_dimension.type:
                    changes.append(_change("dimension.type_changed", dimension_path, base_dimension.type, head_dimension.type))
                if base_dimension.granularity != head_dimension.granularity:
                    changes.append(
                        _change(
                            "dimension.granularity_changed",
                            dimension_path,
                            base_dimension.granularity,
                            head_dimension.granularity,
                        )
                    )

    for metric_name in sorted(set(base.metrics) | set(head.metrics)):
        base_metric = base.metrics.get(metric_name)
        head_metric = head.metrics.get(metric_name)
        path = f"metrics.{metric_name}"

        if base_metric is None and head_metric is not None:
            changes.append(_change("metric.added", path, None, head_metric.model_dump(mode="json")))
            continue
        if base_metric is not None and head_metric is None:
            changes.append(_change("metric.removed", path, base_metric.model_dump(mode="json"), None))
            continue
        assert base_metric is not None and head_metric is not None

        _diff_metric(path, base_metric, head_metric, changes)

    return changes


def _diff_metric(path: str, base_metric: MetricContract, head_metric: MetricContract, changes: list[ChangeRecord]) -> None:
    if base_metric.metric_type != head_metric.metric_type:
        changes.append(_change("metric.type_changed", path, base_metric.metric_type, head_metric.metric_type))
        return

    if base_metric.owner_model != head_metric.owner_model:
        changes.append(_change("metric.owner_model_changed", path, base_metric.owner_model, head_metric.owner_model))
    if base_metric.label != head_metric.label:
        changes.append(_change("metric.label_changed", path, base_metric.label, head_metric.label))
    if base_metric.filter != head_metric.filter:
        changes.append(_change("metric.filter_changed", path, base_metric.filter, head_metric.filter))
    if base_metric.agg_time_dimension != head_metric.agg_time_dimension:
        changes.append(
            _change(
                "metric.agg_time_dimension_changed",
                path,
                base_metric.agg_time_dimension,
                head_metric.agg_time_dimension,
            )
        )

    if base_metric.metric_type == "simple":
        if base_metric.agg != head_metric.agg:
            changes.append(_change("metric.simple.agg_changed", path, base_metric.agg, head_metric.agg))
        if base_metric.expr != head_metric.expr:
            changes.append(_change("metric.simple.expr_changed", path, base_metric.expr, head_metric.expr))
        if base_metric.non_additive_dimension != head_metric.non_additive_dimension:
            changes.append(
                _change(
                    "metric.simple.non_additive_dimension_changed",
                    path,
                    base_metric.non_additive_dimension,
                    head_metric.non_additive_dimension,
                )
            )
    elif base_metric.metric_type == "ratio":
        if base_metric.numerator != head_metric.numerator:
            changes.append(_change("metric.ratio.numerator_changed", path, base_metric.numerator, head_metric.numerator))
        if base_metric.denominator != head_metric.denominator:
            changes.append(
                _change("metric.ratio.denominator_changed", path, base_metric.denominator, head_metric.denominator)
            )
    elif base_metric.metric_type == "derived":
        if base_metric.expr != head_metric.expr:
            changes.append(_change("metric.derived.expr_changed", path, base_metric.expr, head_metric.expr))
        if base_metric.input_metrics != head_metric.input_metrics:
            changes.append(
                _change("metric.derived.inputs_changed", path, base_metric.input_metrics, head_metric.input_metrics)
            )


def _change(code: str, path: str, before: object, after: object) -> ChangeRecord:
    return ChangeRecord(
        code=code,
        severity=SEVERITY_BY_CODE[code],
        path=path,
        before=before,
        after=after,
        message=_describe_change(code, path, before, after),
    )


def _describe_change(code: str, path: str, before: object, after: object) -> str:
    name = path.split(".")[-1]
    messages = {
        "semantic_model.added": f"Semantic model `{name}` was added.",
        "semantic_model.removed": f"Semantic model `{name}` was removed.",
        "semantic_model.model_changed": f"Semantic model `{name}` changed backing model from `{before}` to `{after}`.",
        "semantic_model.agg_time_dimension_changed": (
            f"Semantic model `{name}` changed default aggregation time dimension from `{before}` to `{after}`."
        ),
        "entity.added": f"Entity `{name}` was added.",
        "entity.removed": f"Entity `{name}` was removed.",
        "entity.type_changed": f"Entity `{name}` changed type from `{before}` to `{after}`.",
        "dimension.added": f"Dimension `{name}` was added.",
        "dimension.removed": f"Dimension `{name}` was removed.",
        "dimension.type_changed": f"Dimension `{name}` changed type from `{before}` to `{after}`.",
        "dimension.granularity_changed": f"Dimension `{name}` changed granularity from `{before}` to `{after}`.",
        "metric.added": f"Metric `{name}` was added.",
        "metric.removed": f"Metric `{name}` was removed.",
        "metric.type_changed": f"Metric `{name}` changed type from `{before}` to `{after}`.",
        "metric.owner_model_changed": f"Metric `{name}` changed owning semantic model from `{before}` to `{after}`.",
        "metric.label_changed": f"Metric `{name}` changed label from `{before}` to `{after}`.",
        "metric.filter_changed": f"Metric `{name}` changed filter from `{before}` to `{after}`.",
        "metric.agg_time_dimension_changed": (
            f"Metric `{name}` changed aggregation time dimension from `{before}` to `{after}`."
        ),
        "metric.simple.agg_changed": f"Metric `{name}` changed aggregation from `{before}` to `{after}`.",
        "metric.simple.expr_changed": f"Metric `{name}` changed expression from `{before}` to `{after}`.",
        "metric.simple.non_additive_dimension_changed": (
            f"Metric `{name}` changed non-additive dimension from `{before}` to `{after}`."
        ),
        "metric.ratio.numerator_changed": f"Metric `{name}` changed numerator from `{before}` to `{after}`.",
        "metric.ratio.denominator_changed": f"Metric `{name}` changed denominator from `{before}` to `{after}`.",
        "metric.derived.inputs_changed": f"Metric `{name}` changed derived inputs from `{before}` to `{after}`.",
        "metric.derived.expr_changed": f"Metric `{name}` changed derived expression from `{before}` to `{after}`.",
    }
    return messages[code]
