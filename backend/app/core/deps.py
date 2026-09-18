"""FastAPI 依赖：用户 JWT / 角色 / 权限 / 机器共享 token（迁自旧 auth.py）。"""
from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException

from app import crud
from app.core import security
from app.services import state


def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = security.decode_token(authorization[7:].strip())
    if not payload:
        raise HTTPException(401, "invalid or expired token")
    user = crud.get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "user not found")
    return user


def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "admin required")
    return user


def require_perm(perm: str):
    """依赖工厂：admin 隐式全权限；user 需 permissions 里含 perm。"""
    def _dep(user: dict = Depends(require_user)) -> dict:
        if user.get("role") == "admin" or perm in (user.get("permissions") or []):
            return user
        raise HTTPException(403, f"缺少权限：{perm}")
    return _dep


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = state.get_ingest_config().get("api_token", "").strip()
    if not expected:
        # fail-closed：没配 token 就拒绝机器接入，避免默认开放
        raise HTTPException(503, "机器接入未启用：未配置 API token")
    if not x_api_token or not hmac.compare_digest(x_api_token.encode(), expected.encode()):
        raise HTTPException(401, "invalid or missing API token")
