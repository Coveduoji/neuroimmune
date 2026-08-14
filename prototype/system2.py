"""系统2（认知层）——贵模型，只在被精确唤醒时深想。

现在对「一个案件」（一组共享实体的关联信号）做结构化调查，输出严格 JSON，
而不是自由文本。反幻觉纪律来自 agentic-soc-platform 的实践：只用事实、
不编造、区分事实/推论/未确认、证据不足就降 confidence 并写 unknowns——
这正是「置信度」这一命门的解法：逼模型承认不确定，而不是硬给高分。
"""
from __future__ import annotations

import json

from amygdala import _extract_json
from blackboard import Event
from llm import ModelClient

INVESTIGATION_SYSTEM = (
    "你是资深 SOC 调查分析师。给你一个「案件」——一组共享实体的关联信号，"
    "产出一个 JSON 对象，字段如下：\n"
    "verdict: 定性，取 True Positive / Suspicious / False Positive / Benign / Insufficient Data\n"
    "confidence: High / Medium / Low\n"
    "digest: 4-6 句的高信息密度结论\n"
    "evidence: 证据发现数组，每项 {fact: 可追溯的事实, conclusion: 它对判断意味着什么}\n"
    "attack_chain: 攻击链阶段数组，每项 {phase: MITRE 阶段, description: 发生了什么+依据}，无证据就空\n"
    "iocs: 可复用 IOC 数组，每项 {value, context}，无就空\n"
    "remediations: 具体可执行的处置建议数组，别写「加强监控」这种空泛建议\n"
    "unknowns: 尚未确认的关键缺口数组\n"
    "纪律：只用输入里的事实，不编造证据；区分「已观察事实 / 推论 / 未确认」；"
    "证据不足就降 confidence 并在 unknowns 写清缺口；列表宁可空也不凑数；只输出 JSON，不要其他文字。"
)


def _event_dict(e: Event) -> dict:
    return {
        "time": e.time, "source": e.source, "asset": e.asset,
        "type": e.etype, "confidence": round(e.confidence, 2), "raw": e.raw,
    }


def deep_analyze_chain(events: list[Event], client: ModelClient, knowledge: list[str] | None = None) -> dict:
    """对一个案件（一组关联信号）做结构化调查，返回 dict（严格 JSON）。

    knowledge 是记忆 RAG 检索到的「过去的处置经验」，作为参考注入，但以当前证据为准。
    """
    ctx = "案件信号列表：\n" + json.dumps(
        [_event_dict(e) for e in events], ensure_ascii=False, indent=2
    )
    if knowledge:
        ctx += (
            "\n\n过去的处置经验（历史参考，不是当前事实，需结合当前案件证据判断）：\n"
            + "\n".join(f"- {k}" for k in knowledge)
        )
    raw = client.analyze(INVESTIGATION_SYSTEM + "\n\n" + ctx)
    return _extract_json(raw)
