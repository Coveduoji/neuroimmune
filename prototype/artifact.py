"""实体抽取（Artifact 层）——把一条信号里的「实体」单独拆出来。

一条告警里往往装着多个实体（账号、主机、源 IP、文件哈希…），但我们的信号
只有扁平的 asset 字段。这里把 asset + raw 正文里的 IP / 哈希 / 域名 / 带分隔符的
标识符都抽出来，供「图」做关联——拼链不再只靠 asset 一个字段，而是靠任意共享实体。

抽取是启发式的（正则），够 demo 用；生产里应由各告警源的 Module 精确解析。
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    type: str   # asset / ip / hash / domain / id
    value: str


_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HASH = re.compile(r"\b[0-9a-fA-F]{32}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b")
# 完整 FQDN（多级标签 + 顶级域）：mall-portal.example.com 匹配成一个域名，而不是
# 被拆成 example.com（域）+ mall-portal（标识符）两个节点。
_DOMAIN = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|io|net|org|cn|cloud|local|lan|internal)\b", re.IGNORECASE)
# 带分隔符、以字母开头的标识符：svc_backup / payroll-db-03 / backup-oss / web-01
_IDENT = re.compile(r"\b[a-zA-Z]\w*(?:[_-][\w-]*)+\b")


def extract_entities(signal: dict) -> list[Entity]:
    """从一条信号里抽实体，去重、保持顺序。

    实体归一化：按「值」归类——IP 归为 ip，其余（主机/账号/标识符）归为 asset。
    这样同一台主机无论在 asset 字段还是正文里出现，都是同一个实体，不再拆成多个节点。
    """
    entities: list[Entity] = []

    asset = (signal.get("asset") or "").strip()
    if asset:
        etype = "ip" if _IP.fullmatch(asset) else "asset"
        entities.append(Entity(etype, asset))

    raw = signal.get("raw") or ""
    domains = _DOMAIN.findall(raw)
    # 域名里的每一级标签不再单独当标识符：mall-portal.example.com 只出域名，不另出 mall-portal
    domain_labels = {lab.lower() for d in domains for lab in d.split(".")}
    for ip in _IP.findall(raw):
        entities.append(Entity("ip", ip))
    for h in _HASH.findall(raw):
        entities.append(Entity("hash", h.lower()))
    for d in domains:
        entities.append(Entity("domain", d.lower()))
    for ident in _IDENT.findall(raw):
        if ident.lower() != asset.lower() and ident.lower() not in domain_labels:
            entities.append(Entity("asset", ident))  # 标识符归为 asset，不再用 id

    seen: set[tuple[str, str]] = set()
    out: list[Entity] = []
    for e in entities:
        k = (e.type, e.value)
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out
