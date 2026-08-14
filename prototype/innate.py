"""固有免疫（免疫层）——规则引擎，只会认见过的，但秒拦、不花钱。

把「已确认的攻击模式」按签名写进规则（signature.py 的告警形状）；下次信号命中同形状，
直接在边缘秒拦——连杏仁核都不用叫，系统2 更不用醒。

与免疫耐受（tolerance.py）对称：耐受记「已知好」→ 静默，固有免疫记「已知坏」→ 秒拦。
规则持久化在 data/innate_rules.json，签名匹配（比 (asset, type) 更细）。
"""
from __future__ import annotations

import json
import os

from signature import signature

INNATE_PATH = os.path.join(os.path.dirname(__file__), "data", "innate_rules.json")


def load_rules() -> set[str]:
    if not os.path.exists(INNATE_PATH):
        return set()
    with open(INNATE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # 只收签名字符串；旧格式 [asset, type] 列表会被过滤掉（= 重置，不可逆）
    return {e for e in data if isinstance(e, str)}


def save_rules(rules: set[str]) -> None:
    with open(INNATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(rules), f, ensure_ascii=False, indent=2)


def match(signal: dict, rules: set[str]) -> bool:
    """同「形状」的信号已在规则里 → 已知坏，边缘秒拦。"""
    return signature(signal.get("source", ""), signal.get("type", ""), signal.get("raw", "")) in rules


def add(rules: set[str], sigs: list[str]) -> list[str]:
    """把新的签名加进规则，返回本次新增的。"""
    new = [s for s in sigs if s not in rules]
    rules.update(new)
    return new
