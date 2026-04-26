from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def _strip_diagnostics(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_diagnostics(item) for key, item in value.items() if key != "source"}
    if isinstance(value, list):
        return [_strip_diagnostics(item) for item in value]
    return value


def _strip_null_sources(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "source" and item is None:
                continue
            result[key] = _strip_null_sources(item)
        return result
    if isinstance(value, list):
        return [_strip_null_sources(item) for item in value]
    return value


@dataclass(eq=False)
class SemanticComparableModel:
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _strip_null_sources(asdict(self))

    def model_dump_json(self, indent: int | None = None, **kwargs: Any) -> str:
        return json.dumps(self.model_dump(), indent=indent)

    def semantic_dump(self) -> dict[str, Any]:
        return _strip_diagnostics(self.model_dump())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.semantic_dump() == other.semantic_dump()
        return NotImplemented


@dataclass(eq=False)
class SourceLocation:
    file: str
    line: int
    end_line: int | None = None

    def display(self) -> str:
        return f"{self.file}:{self.line}"
        
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SourceLocation | None:
        if not data:
            return None
        return cls(**data)


@dataclass(eq=False)
class EntityContract(SemanticComparableModel):
    name: str
    type: str
    expr: str
    source: SourceLocation | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityContract:
        return cls(
            name=data["name"],
            type=data["type"],
            expr=data["expr"],
            source=SourceLocation.from_dict(data.get("source")),
        )


@dataclass(eq=False)
class DimensionContract(SemanticComparableModel):
    name: str
    type: str
    expr: str
    granularity: str | None = None
    source: SourceLocation | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DimensionContract:
        return cls(
            name=data["name"],
            type=data["type"],
            expr=data["expr"],
            granularity=data.get("granularity"),
            source=SourceLocation.from_dict(data.get("source")),
        )


@dataclass(eq=False)
class MeasureContract(SemanticComparableModel):
    name: str
    agg: str | None = None
    expr: str | None = None
    agg_time_dimension: str | None = None
    non_additive_dimension: dict[str, Any] | None = None
    source: SourceLocation | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeasureContract:
        return cls(
            name=data["name"],
            agg=data.get("agg"),
            expr=data.get("expr"),
            agg_time_dimension=data.get("agg_time_dimension"),
            non_additive_dimension=data.get("non_additive_dimension"),
            source=SourceLocation.from_dict(data.get("source")),
        )


@dataclass(eq=False)
class MetricContract(SemanticComparableModel):
    name: str
    metric_type: str
    label: str | None = None
    agg: str | None = None
    expr: str | None = None
    filter: str | None = None
    agg_time_dimension: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    input_metrics: list[str] = field(default_factory=list)
    input_metric: str | None = None
    window: str | None = None
    grain_to_date: str | None = None
    period_agg: str | None = None
    entity: str | None = None
    calculation: str | None = None
    base_metric: str | None = None
    conversion_metric: str | None = None
    constant_properties: str | None = None
    non_additive_dimension: dict[str, Any] | None = None
    owner_model: str | None = None
    source: SourceLocation | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricContract:
        return cls(
            name=data["name"],
            metric_type=data.get("type", data.get("metric_type", "")),
            label=data.get("label"),
            agg=data.get("agg"),
            expr=data.get("expr"),
            filter=data.get("filter"),
            agg_time_dimension=data.get("agg_time_dimension"),
            numerator=data.get("numerator"),
            denominator=data.get("denominator"),
            input_metrics=data.get("input_metrics", []),
            input_metric=data.get("input_metric"),
            window=data.get("window"),
            grain_to_date=data.get("grain_to_date"),
            period_agg=data.get("period_agg"),
            entity=data.get("entity"),
            calculation=data.get("calculation"),
            base_metric=data.get("base_metric"),
            conversion_metric=data.get("conversion_metric"),
            constant_properties=data.get("constant_properties"),
            non_additive_dimension=data.get("non_additive_dimension"),
            owner_model=data.get("owner_model"),
            source=SourceLocation.from_dict(data.get("source")),
        )


@dataclass(eq=False)
class SemanticModelContract(SemanticComparableModel):
    name: str
    model_name: str
    agg_time_dimension: str | None = None
    entities: dict[str, EntityContract] = field(default_factory=dict)
    dimensions: dict[str, DimensionContract] = field(default_factory=dict)
    measures: dict[str, MeasureContract] = field(default_factory=dict)
    source: SourceLocation | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticModelContract:
        return cls(
            name=data["name"],
            model_name=data["model_name"],
            agg_time_dimension=data.get("agg_time_dimension"),
            entities={k: EntityContract.from_dict(v) for k, v in data.get("entities", {}).items()},
            dimensions={k: DimensionContract.from_dict(v) for k, v in data.get("dimensions", {}).items()},
            measures={k: MeasureContract.from_dict(v) for k, v in data.get("measures", {}).items()},
            source=SourceLocation.from_dict(data.get("source")),
        )


@dataclass(eq=False)
class SemanticContract(SemanticComparableModel):
    semantic_models: dict[str, SemanticModelContract] = field(default_factory=dict)
    metrics: dict[str, MetricContract] = field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: str) -> SemanticContract:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticContract:
        return cls(
            semantic_models={k: SemanticModelContract.from_dict(v) for k, v in data.get("semantic_models", {}).items()},
            metrics={k: MetricContract.from_dict(v) for k, v in data.get("metrics", {}).items()},
        )


@dataclass(eq=False)
class ChangeRecord:
    code: str
    severity: str
    message: str
    path: str
    before: Any = None
    after: Any = None
    source: SourceLocation | None = None
    
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _strip_null_sources(asdict(self))


@dataclass(eq=False)
class Report:
    summary: dict[str, int]
    highest_severity: str
    blocking: bool
    changes: list[ChangeRecord]
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "highest_severity": self.highest_severity,
            "blocking": self.blocking,
            "changes": [c.model_dump() for c in self.changes],
            "metadata": self.metadata,
        }
