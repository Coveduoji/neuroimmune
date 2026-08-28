"""夜间巩固（睡眠巩固）——定时从 SQLite 蒸馏，把一天的案件沉淀成检索记忆。

对应 README 的「记忆」层。和 prototype/consolidate.py 的区别：这里直接读后端的 SQLite
（流式入库的案件），不读批处理的 history.jsonl。只做一件事：把当天案件用深想模型蒸馏成
{summary, ttps, false_positives}，追加到 memory.jsonl，供系统2 调查时 RAG 检索。

注意：
- 固有免疫规则**不**由夜间巩固回写——规则只由分析师「标记真阳性」写入
  （backend/api/cases.py 的 true_positive），避免未确认的误报被永久写进「已知坏」。
- 模块名用 nightly，避开 prototype/consolidate.py 的同名冲突。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from amygdala import _extract_json

import db
import state
from paths import MEMORY_PATH

CONSOLIDATE_SYSTEM = (
    "你是安全系统的「睡眠巩固」，负责夜里把一天的安全案件整合成记忆。"
    "给你当天案件列表（JSON），输出一个 JSON 对象，字段：\n"
    "summary: 一句话中文总结\n"
    "ttps: 提炼的攻击手法数组（可空）\n"
    "false_positives: 观察到的误报模式数组（可空）\n"
    "只输出 JSON，不要其他文字。"
)


def _append_memory(record: dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def consolidate() -> dict:
    db.init_db()
    deep = state.get_deep_client()
    cases = db.list_cases(limit=1000)
    if not cases:
        return {"status": "empty", "memory": None}

    # 睡眠巩固整合 → 检索记忆
    context = []
    for c in cases:
        alerts = db.get_case_alerts(c["id"])
        report = db.get_case_report(c["id"])
        context.append({
            "case": c["correlation_uid"], "title": c["title"], "strength": c["strength"],
            "verdict": c.get("verdict", ""), "note": c.get("disposition_note", ""),
            "alerts": [{"time": a["time"], "source": a["source"], "type": a["type"], "raw": a["raw"]} for a in alerts],
            "ai_digest": report.get("digest", "") if report else "",
        })
    record = _extract_json(deep.analyze(CONSOLIDATE_SYSTEM + json.dumps(context, ensure_ascii=False, indent=2)))
    _append_memory(record)
    # 注意：固有免疫规则只由分析师「标记真阳性」写入，夜间巩固不再自动蒸馏，
    # 避免未确认的误报被永久写进「已知坏」规则。
    return {"status": "ok", "memory": record.get("summary", "")}
