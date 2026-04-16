from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityContract(BaseModel):
    name: str
    type: str
    expr: str


class DimensionContract(BaseModel):
    name: str
    type: str
    expr: str
    granularity: str | None = None


class MetricContract(BaseModel):
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
    non_additive_dimension: dict[str, Any] | None = None
    owner_model: str | None = None

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("by_alias", False)
        return super().model_dump(*args, **kwargs)


class SemanticModelContract(BaseModel):
    name: str
    model_name: str
    agg_time_dimension: str | None = None
    entities: dict[str, EntityContract] = Field(default_factory=dict)
    dimensions: dict[str, DimensionContract] = Field(default_factory=dict)


class SemanticContract(BaseModel):
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


class Report(BaseModel):
    summary: dict[str, int]
    highest_severity: str
    blocking: bool
    changes: list[ChangeRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)
