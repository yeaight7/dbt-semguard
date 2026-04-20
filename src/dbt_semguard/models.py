from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class SemanticComparableModel(BaseModel):
    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return _strip_null_sources(super().model_dump(*args, **kwargs))

    def semantic_dump(self) -> dict[str, Any]:
        return _strip_diagnostics(self.model_dump(mode="json"))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.semantic_dump() == other.semantic_dump()
        return NotImplemented


class SourceLocation(BaseModel):
    file: str
    line: int
    end_line: int | None = None

    def display(self) -> str:
        return f"{self.file}:{self.line}"


class EntityContract(SemanticComparableModel):
    name: str
    type: str
    expr: str
    source: SourceLocation | None = None


class DimensionContract(SemanticComparableModel):
    name: str
    type: str
    expr: str
    granularity: str | None = None
    source: SourceLocation | None = None


class MetricContract(SemanticComparableModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    metric_type: str = Field(alias="type")
    label: str | None = None
    agg: str | None = None
    expr: str | None = None
    filter: str | None = None
    agg_time_dimension: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    input_metrics: list[str] = Field(default_factory=list)
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

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("by_alias", False)
        return super().model_dump(*args, **kwargs)


class SemanticModelContract(SemanticComparableModel):
    name: str
    model_name: str
    agg_time_dimension: str | None = None
    entities: dict[str, EntityContract] = Field(default_factory=dict)
    dimensions: dict[str, DimensionContract] = Field(default_factory=dict)
    source: SourceLocation | None = None


class SemanticContract(SemanticComparableModel):
    semantic_models: dict[str, SemanticModelContract] = Field(default_factory=dict)
    metrics: dict[str, MetricContract] = Field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: str) -> "SemanticContract":
        import json
        from pathlib import Path

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(payload)


class ChangeRecord(BaseModel):
    code: str
    severity: str
    message: str
    path: str
    before: Any = None
    after: Any = None
    source: SourceLocation | None = None


class Report(BaseModel):
    summary: dict[str, int]
    highest_severity: str
    blocking: bool
    changes: list[ChangeRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)
