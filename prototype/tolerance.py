"""免疫耐受（免疫层的压误报件）——杏仁核的配套，README 说二者「不能单独上」。

误报反馈回路：把被确认是「正常业务」的信号，按「签名」写进白名单（signature.py 里的
告警形状，掩码掉 IP/哈希/数字，保留主机/账号/描述）。下次杏仁核再看到同形状的信号就
直接静默，连便宜模型都不用叫——既压误报又省算力。白名单持久化在 data/tolerance.json。

比 (asset, type) 更细：签名区分「svc_backup 登录跳板机」和「svc_backup 登录数据库」，
只静默前者，不再漏掉同一资产上的真实攻击。
"""
from __future__ import annotations

import json
import os

from signature import signature

TOLERANCE_PATH = os.path.join(os.path.dirname(__file__), "data", "tolerance.json")


def load_tolerance() -> set[str]:
    if not os.path.exists(TOLERANCE_PATH):
        return set()
    with open(TOLERANCE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # 只收签名字符串；旧格式 [asset, type] 列表会被过滤掉（= 重置，不可逆）
    return {e for e in data if isinstance(e, str)}


def save_tolerance(entries: set[str]) -> None:
    with open(TOLERANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(entries), f, ensure_ascii=False, indent=2)


def is_tolerated(signal: dict, entries: set[str]) -> bool:
    """同「形状」的信号已在白名单 → 已耐受，直接静默。"""
    return signature(signal.get("source", ""), signal.get("type", ""), signal.get("raw", "")) in entries


def learn(entries: set[str], sigs: list[str]) -> list[str]:
    """把新的签名加进白名单，返回本次新增的。"""
    new = [s for s in sigs if s not in entries]
    entries.update(new)
    return new
