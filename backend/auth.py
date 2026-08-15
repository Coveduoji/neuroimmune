"""鉴权：机器共享 token（写操作）+ 用户 JWT（登录后的人）。

- `require_token`：可选的共享 token（X-API-Token），保护机器入库/清库等，默认不设不鉴权。
- 用户体系：用户名/密码 → bcrypt 哈希存 users 表；登录发 JWT（HS256，24h），`require_user`
  校验 Bearer token，`require_admin` 再加角色校验。
- JWT 密钥：环境变量 NEUROIMMUNE_JWT_SECRET 优先；否则首次自动生成并持久化到 secret.key。
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

import bcrypt
import jwt as pyjwt
from fastapi import Depends, Header, HTTPException

import db
import state

ALGORITHM = "HS256"
TOKEN_TTL = 24 * 3600  # 24h
SECRET_PATH = Path(__file__).resolve().parent / "secret.key"


# ---- 机器共享 token（保留）----

def require_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = state.get_ingest_config().get("api_token", "").strip() \
        or os.environ.get("NEUROIMMUNE_API_TOKEN", "").strip()
    if expected and x_api_token != expected:
        raise HTTPException(401, "invalid or missing API token")


# ---- 密码哈希 ----

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---- JWT ----

def _jwt_secret() -> str:
    env = os.environ.get("NEUROIMMUNE_JWT_SECRET", "").strip()
    if env:
        return env
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    SECRET_PATH.write_text(key, encoding="utf-8")
    try:
        os.chmod(SECRET_PATH, 0o600)
    except OSError:
        pass
    return key


def create_access_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return pyjwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except pyjwt.PyJWTError:
        return None


# ---- 用户依赖 ----

def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = decode_token(authorization[7:].strip())
    if not payload:
        raise HTTPException(401, "invalid or expired token")
    user = db.get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "user not found")
    return user


def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "admin required")
    return user


# 权限键目录（键 → 中文说明），前端据此画勾选面板
PERMISSIONS: dict[str, str] = {
    "triage": "分诊：标记误报/真阳性、放回、改案件、外发、免疫规则",
    "config": "配置：旋钮/模型/检测/接入/来源/Webhook/预设/频率/门槛",
    "maintenance": "维护：清库、夜间巩固、上传告警文件",
    "users": "用户管理：建号/删号/改角色/改权限",
}


def require_perm(perm: str):
    """依赖工厂：admin 隐式全权限；user 需 permissions 里含 perm。"""
    def _dep(user: dict = Depends(require_user)) -> dict:
        if user.get("role") == "admin" or perm in (user.get("permissions") or []):
            return user
        raise HTTPException(403, f"缺少权限：{perm}")
    return _dep


# ---- 初始管理员引导 ----

def bootstrap_admin() -> None:
    """启动时确保至少有一个 admin：env 优先，否则建默认 admin/admin（打警告）。"""
    if db.count_admins() > 0:
        return
    env_user = os.environ.get("NEUROIMMUNE_ADMIN_USER", "").strip()
    env_pass = os.environ.get("NEUROIMMUNE_ADMIN_PASSWORD", "").strip()
    if env_user and env_pass:
        username, password = env_user, env_pass
        note = "来自环境变量"
    else:
        username, password = "admin", "admin"
        note = "默认账号，生产请设 NEUROIMMUNE_ADMIN_USER / NEUROIMMUNE_ADMIN_PASSWORD"
    if db.get_user_by_username(username):
        return
    db.create_user(username, hash_password(password), "admin")
    print(f"[auth] 初始管理员已创建：{username}（{note}）")
