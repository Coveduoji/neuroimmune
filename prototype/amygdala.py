"""杏仁核 + 抑制（感知层）——README 里投产比最高、先做的组件。

只做一件事：逐条判「这段里有没有不该发生的」。产出不是告警，而是带置信度的
「不对劲」信号。抑制机制与它一体：置信度低于旋钮阈值的，静默不上报。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm import ModelClient


@dataclass
class Verdict:
    suspicious: bool
    confidence: float
    reason: str


def _extract_json(text: str) -> dict:
    """容错解析模型输出：剥掉 ```json 围栏，抓第一个 {...}。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"模型没输出 JSON：{text!r}")
    return json.loads(text[start : end + 1])


def judge_signal(signal: dict, client: ModelClient) -> Verdict:
    raw = client.judge(signal)
    data = _extract_json(raw)
    confidence = float(data.get("confidence", 0.0))
    return Verdict(
        suspicious=bool(data.get("suspicious", False)),
        confidence=max(0.0, min(1.0, confidence)),
        reason=str(data.get("reason", "")),
    )
