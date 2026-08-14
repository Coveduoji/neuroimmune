"""极简 API 鉴权：可选的共享 token，保护写操作（清库/入库/处置/旋钮）。

默认（不设 token）不鉴权，方便本地开发；部署时在设置页「接入」或环境变量里设即生效。
token 读设置（ingest.json）优先，环境变量 NEUROIMMUNE_API_TOKEN 作为 fallback。
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException

import state


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = state.get_ingest_config().get("api_token", "").strip() \
        or os.environ.get("NEUROIMMUNE_API_TOKEN", "").strip()
    if expected and x_api_token != expected:
        raise HTTPException(401, "invalid or missing API token")
