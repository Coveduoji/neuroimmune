"""睡眠巩固 + 免疫记忆（记忆层）——夜里用贵模型把一天的经验沉淀成记忆 + 回写检测。

README ⑤：夜里（cron）把当天黑板的原始信号、处置、决策整合成结构化记录，两个去向：
(a) 检索记忆库 data/memory.jsonl —— 跨天记住上下文
(b) 回写检测：提炼新 TTP 进固有免疫规则 data/innate_rules.json

跑法：
    python3 consolidate.py          # 读 data/history.jsonl，巩固后写 memory + innate_rules
"""
from __future__ import annotations

import json
import os

import innate
from amygdala import _extract_json
from llm import get_deep_client
from signature import signature

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "history.jsonl")
MEMORY_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.jsonl")

CONSOLIDATE_SYSTEM = (
    "你是安全系统的「睡眠巩固」，负责夜里把一天的安全事件整合成记忆。"
    "给你当天上黑板的事件列表（JSON 数组），请输出一个 JSON 对象，字段如下：\n"
    "summary: 一句话中文总结今天发生了什么\n"
    "ttps: 提炼出的攻击手法/技术（字符串数组，没有就给空数组）\n"
    "false_positives: 观察到的误报模式（字符串数组，没有就给空数组）\n"
    "只输出 JSON，不要任何其他文字。"
)


def _read_history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    out = []
    with open(HISTORY_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _append_memory(record: dict) -> None:
    with open(MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    events = _read_history()
    if not events:
        print("history 为空——先跑 `python3 main.py` 产生当天事件。")
        return

    client = get_deep_client()
    print(f"睡眠巩固后端：{type(client).__name__}，整合 {len(events)} 条事件…")

    raw = client.analyze(
        CONSOLIDATE_SYSTEM + "\n\n当天事件列表：\n"
        + json.dumps(events, ensure_ascii=False, indent=2)
    )
    try:
        record = _extract_json(raw)
    except ValueError as e:
        print(f"睡眠巩固没输出合法 JSON：{e}")
        print("原始输出：", raw)
        return
    _append_memory(record)

    # 回写固有免疫规则：被顶出且非误报的事件 → 提炼成签名字符串（与 backend 一致）
    malicious = [
        signature(e["source"], e["type"], e["raw"], e["asset"])
        for e in events
        if e.get("escalated") and e.get("label") != "benign"
    ]
    new_rules = innate.add_signatures(malicious)

    print("【记忆】summary：", record.get("summary"))
    print("【记忆】TTPs：", record.get("ttps"))
    print("【记忆】误报观察：", record.get("false_positives"))
    print("-" * 64)
    print(f"检索记忆已追加 → data/memory.jsonl")
    print(f"固有免疫新规则 : {new_rules or '（无新增）'} → data/innate_rules.json")
    print("下次 main.py 遇到这些签名会边缘秒拦，连杏仁核都不用叫。")


if __name__ == "__main__":
    main()
