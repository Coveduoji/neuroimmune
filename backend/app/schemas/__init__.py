"""Pydantic 请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class CasePatch(BaseModel):
    status: str | None = None
    severity: str | None = None
    verdict: str | None = None
    note: str | None = None


class KnobSet(BaseModel):
    knob: str


class IngestRequest(BaseModel):
    signals: list[dict]
    knob: str = "正常"
