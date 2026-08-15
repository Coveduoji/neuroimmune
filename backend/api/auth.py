"""用户认证 API：登录 / 当前用户 / 建号 / 用户列表 / 删号 / 改角色 / 改权限。"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

import auth
import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_USER_PERMS = ["triage"]


def _public(u: dict) -> dict:
    return {"id": u["id"], "username": u["username"], "role": u["role"],
            "permissions": u.get("permissions") or [], "created_at": u["created_at"]}


@router.post("/login")
def login(body: dict):
    body = body or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = db.get_user_by_username(username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    return {"token": auth.create_access_token(user), "user": _public(user)}


@router.get("/me")
def me(user: dict = Depends(auth.require_user)):
    return _public(user)


@router.post("/change-password")
def change_password(body: dict, user: dict = Depends(auth.require_user)):
    body = body or {}
    old = body.get("old_password") or ""
    new = body.get("new_password") or ""
    if not new:
        raise HTTPException(400, "新密码不能为空")
    if not auth.verify_password(old, user["password_hash"]):
        raise HTTPException(400, "当前密码错误")
    db.update_user_password(user["id"], auth.hash_password(new))
    return {"ok": True}


@router.get("/permissions")
def list_permissions(_user: dict = Depends(auth.require_user)):
    """权限键目录，前端据此画勾选面板。"""
    return {"items": auth.PERMISSIONS}


@router.post("/register")
def register(body: dict, _admin: dict = Depends(auth.require_perm("users"))):
    body = body or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = body.get("role") or "user"
    if not username or not password:
        raise HTTPException(400, "用户名和密码不能为空")
    if role not in ("admin", "user"):
        raise HTTPException(400, "角色必须是 admin 或 user")
    if db.get_user_by_username(username):
        raise HTTPException(400, "用户名已存在")
    perms = body.get("permissions")
    if perms is None:
        perms = DEFAULT_USER_PERMS if role == "user" else []
    user_id = db.create_user(username, auth.hash_password(password), role, perms)
    return _public(db.get_user(user_id))


@router.get("/users")
def list_users(_admin: dict = Depends(auth.require_perm("users"))):
    return {"items": db.list_users()}


@router.put("/users/{user_id}")
def update_user(user_id: int, body: dict, _admin: dict = Depends(auth.require_perm("users"))):
    """管理员改用户角色（保留最后一个 admin）。"""
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    role = (body or {}).get("role")
    if role and role not in ("admin", "user"):
        raise HTTPException(400, "角色必须是 admin 或 user")
    if role and role != target["role"]:
        if target["role"] == "admin" and db.count_admins() <= 1:
            raise HTTPException(400, "至少保留一个管理员")
        db.update_user(user_id, {"role": role})
    return _public(db.get_user(user_id))


@router.put("/users/{user_id}/permissions")
def update_user_permissions(user_id: int, body: dict, _admin: dict = Depends(auth.require_perm("users"))):
    """管理员配置某用户的权限键列表。"""
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    perms = (body or {}).get("permissions")
    if perms is None:
        raise HTTPException(400, "permissions 必填")
    perms = [p for p in perms if isinstance(p, str)]
    bad = [p for p in perms if p not in auth.PERMISSIONS]
    if bad:
        raise HTTPException(400, f"未知权限：{', '.join(bad)}")
    db.update_user(user_id, {"permissions": json.dumps(perms, ensure_ascii=False)})
    return _public(db.get_user(user_id))


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, body: dict, _admin: dict = Depends(auth.require_perm("users"))):
    """管理员重置某用户密码。"""
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    new = (body or {}).get("new_password") or ""
    if not new:
        raise HTTPException(400, "新密码不能为空")
    db.update_user(user_id, {"password_hash": auth.hash_password(new)})
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(auth.require_perm("users"))):
    target = db.get_user(user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    if target["id"] == admin["id"]:
        raise HTTPException(400, "不能删除自己")
    if target["role"] == "admin" and db.count_admins() <= 1:
        raise HTTPException(400, "至少保留一个管理员")
    db.delete_user(user_id)
    return {"ok": True}
