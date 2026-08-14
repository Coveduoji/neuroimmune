"""最小闭环 demo：信号 → 耐受/固有免疫 → 杏仁核 → 黑板 → 图（拼链归案）→ 系统2（结构化调查）。

跑法：
    cd prototype && python3 main.py                          # 读内置样例 data/sample.jsonl
    cd prototype && python3 main.py --input alerts.jsonl      # 读你自己的告警导出
    cd prototype && python3 main.py --knob 战时               # 换风险旋钮

接真实开源模型：直接编辑 prototype/.env（llm.py 会自动读取），填上 key 即可。
"""
from __future__ import annotations

import argparse
import json
import os

import amygdala
import artifact
import blackboard
import config
import graph
import innate
import signals
import system2
import tolerance
from llm import get_client, get_deep_client

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "data", "history.jsonl")
LAST_RUN_PATH = os.path.join(os.path.dirname(__file__), "data", "last_run.json")


def _write_history(board: blackboard.Blackboard, esc_event_ids: set) -> None:
    """把当天上黑板的事件写进 history.jsonl，作为夜里「睡眠巩固」的原料。"""
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        for e in board.events:
            f.write(json.dumps({
                "time": e.time, "source": e.source, "asset": e.asset, "type": e.etype,
                "confidence": round(e.confidence, 2), "raw": e.raw, "reason": e.reason,
                "label": e.label, "innate": e.innate, "escalated": id(e) in esc_event_ids,
            }, ensure_ascii=False) + "\n")


def _write_last_run(*, knob, path, counts, board, comp_uid, esc_event_ids, deep_reports, suppressed_log, learned, system1, system2) -> None:
    """把本轮完整结果写进 last_run.json，供 visualize.py 生成路由观测页。

    关键产品决策：抑制不是「丢弃」，是「降级留痕」；黑板上所有事件（含未顶出的）
    都进 board；图连通分量 + correlation_uid 是「硬归案」的证据。
    """
    payload = {
        "knob": {"name": knob.name, "suppress_below": knob.suppress_below,
                 "escalate_above": knob.escalate_above, "budget": knob.budget},
        "input": path,
        "system1_backend": system1,
        "system2_backend": system2,
        "counts": counts,
        "board": [
            {"time": e.time, "source": e.source, "asset": e.asset, "type": e.etype,
             "confidence": round(e.confidence, 2), "raw": e.raw, "reason": e.reason,
             "innate": e.innate, "label": e.label,
             "correlation_uid": comp_uid.get(id(e), ""),
             "escalated": id(e) in esc_event_ids}
            for e in board.events
        ],
        "graph": _serialize_graph(board, comp_uid),
        "deep_reports": deep_reports,
        "suppressed": suppressed_log,
        "learned_tolerance": [list(k) for k in learned],
    }
    with open(LAST_RUN_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _serialize_graph(board: blackboard.Blackboard, comp_uid: dict) -> dict:
    """把黑板上事件的实体图序列化，供可视化画节点/边/分量。"""
    g = graph.Graph()
    for i, e in enumerate(board.events):
        ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})
        if ents:
            g.add_signal(i, ents)
    sig_comp = graph.signal_components(g)
    nodes = [{"type": e.type, "value": e.value} for e in g.entities]
    edges = [[a, b] for a, b in g.edges]
    comps = []
    for cid, members in enumerate(g.components()):
        ents = [g.entities[i] for i in members]
        comps.append({
            "id": graph.component_id(ents),
            "entities": [{"type": e.type, "value": e.value} for e in ents],
        })
    return {"nodes": nodes, "edges": edges, "components": comps, "signal_components": sig_comp}


def _build_graph(board: blackboard.Blackboard):
    g = graph.Graph()
    for i, e in enumerate(board.events):
        ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})
        if ents:
            g.add_signal(i, ents)
    return g


def run(knob_name: str, input_path: str | None) -> None:
    knob = config.get_knob(knob_name)
    client = get_client()
    deep_client = get_deep_client()
    board = blackboard.Blackboard()
    tol = tolerance.load_tolerance()
    innate_rules = innate.load_rules()

    path = input_path or signals.SAMPLE_PATH
    total = innate_hits = tol_suppressed = suppressed = surfaced = 0
    benign_keys: list[tuple[str, str]] = []
    suppressed_log: list[dict] = []  # 被抑制信号的审计留痕（降级留痕，可查，不静默）

    print(f"风险旋钮：{knob.name}（抑制线 {knob.suppress_below} / 顶出线 {knob.escalate_above} / 预算 {knob.budget}）")
    print(f"杏仁核后端：{type(client).__name__}")
    print(f"系统2后端  : {type(deep_client).__name__}")
    print(f"信号来源：{path}")
    print(f"免疫耐受白名单：{sorted(tol) or '（空）'}")
    print(f"固有免疫规则  : {sorted(innate_rules) or '（空）'}")
    print("-" * 64)

    for sig in signals.load_signals(path):
        total += 1

        # 免疫耐受：白名单命中 → 降级留痕，连便宜模型都不用叫（压误报 + 省算力）
        if tolerance.is_tolerated(sig, tol):
            tol_suppressed += 1
            suppressed_log.append({
                "time": sig["time"], "source": sig["source"], "asset": sig["asset"],
                "type": sig["type"], "raw": sig["raw"], "confidence": None,
                "why": "免疫耐受：已知好，白名单降级",
            })
            continue

        # 固有免疫：命中已知坏规则 → 边缘秒拦，连杏仁核都不用叫，系统2更不用醒
        if innate.match(sig, innate_rules):
            innate_hits += 1
            surfaced += 1
            board.post(
                blackboard.Event(
                    time=sig["time"], source=sig["source"], asset=sig["asset"],
                    etype=sig["type"], confidence=0.95, raw=sig["raw"],
                    reason="固有免疫秒拦：已知攻击家族", label=sig.get("label", ""), innate=True,
                )
            )
            continue

        # ground-truth 标注的「正常业务」→ 记下来准备写进白名单（免疫耐受回写）
        if sig.get("label") == "benign":
            benign_keys.append((sig["asset"], sig["type"]))

        v = amygdala.judge_signal(sig, client)

        # 抑制机制：置信度低于抑制线 → 降级留痕（可审计），不上黑板（压误报）
        if v.confidence < knob.suppress_below:
            suppressed += 1
            suppressed_log.append({
                "time": sig["time"], "source": sig["source"], "asset": sig["asset"],
                "type": sig["type"], "raw": sig["raw"], "confidence": round(v.confidence, 2),
                "why": f"杏仁核低置信度（{v.confidence:.2f} < 抑制线 {knob.suppress_below}）",
            })
            continue

        surfaced += 1
        board.post(
            blackboard.Event(
                time=sig["time"], source=sig["source"], asset=sig["asset"],
                etype=sig["type"], confidence=v.confidence,
                raw=sig["raw"], reason=v.reason, label=sig.get("label", ""),
            )
        )

    # —— 图：实体为点、共现为边，连通分量 = 案件/攻击链 ——
    g = _build_graph(board)
    sig_comp = graph.signal_components(g)
    comps = g.components()

    comp_event_idxs: dict[int, list[int]] = {}
    for i, cid in enumerate(sig_comp):
        if cid >= 0:
            comp_event_idxs.setdefault(cid, []).append(i)

    def strength(idxs: list[int]) -> float:
        confs = [board.events[i].confidence for i in idxs]
        return max(confs) + min(0.30, 0.10 * (len(idxs) - 1))

    ranked = sorted(comp_event_idxs.items(), key=lambda kv: strength(kv[1]), reverse=True)
    escalated = [(cid, idxs) for cid, idxs in ranked if strength(idxs) >= knob.escalate_above]

    # 每个分量一个稳定的 correlation_uid
    comp_uid: dict[int, str] = {}
    for cid in comp_event_idxs:
        comp_uid[cid] = graph.component_id([g.entities[i] for i in comps[cid]])

    # 事件 → correlation_uid / 是否顶出
    event_uid: dict[int, str] = {}
    esc_event_ids: set = set()
    for cid, idxs in comp_event_idxs.items():
        uid = comp_uid[cid]
        is_esc = cid in {c[0] for c in escalated}
        for i in idxs:
            e = board.events[i]
            event_uid[id(e)] = uid
            if is_esc:
                esc_event_ids.add(id(e))

    _write_history(board, esc_event_ids)

    learned = tolerance.learn(tol, benign_keys)
    if learned:
        tolerance.save_tolerance(tol)

    # 系统2：预算内、且含「非固有免疫」事件的分量才深想（已知家族不用再想）
    def has_non_innate(idxs: list[int]) -> bool:
        return any(not board.events[i].innate for i in idxs)

    candidates = [(cid, idxs) for cid, idxs in escalated if has_non_innate(idxs)]
    wake = candidates[:knob.budget]
    wake_cids = {cid for cid, _ in wake}
    saved = [c for c in escalated if c[0] not in wake_cids]

    print(f"信号总数      : {total}")
    print(f"耐受抑制      : {tol_suppressed} 条（白名单直接静默，没叫模型）")
    print(f"固有免疫秒拦  : {innate_hits} 条（已知坏规则命中，没叫模型）")
    print(f"杏仁核抑制    : {suppressed} 条（噪声被静默）")
    print(f"上板          : {surfaced} 条")
    print(f"归案分量      : {len(comp_event_idxs)} 个（图连通分量）")
    print(f"顶出案件      : {len(escalated)} 个（强度越过顶出线）")
    print(f"唤醒系统2     : {len(wake)} 个（预算 {knob.budget}，真调贵模型）")
    print(f"省下深度算力  : {len(saved)} 个（顶出但预算不够 / 已知家族）")
    print("-" * 64)

    if escalated:
        print("【顶出案件，按强度降序】")
        for cid, idxs in escalated:
            ents = [g.entities[i] for i in comps[cid]]
            tag = ""
            if not has_non_innate(idxs):
                tag = "  ← 固有免疫秒拦，系统2没醒"
            print(f"  案件 {comp_uid[cid]}  强度 {strength(idxs):.2f}  {len(idxs)} 条信号{tag}")
            print(f"      实体：{', '.join(f'{e.value}({e.type})' for e in ents)}")
            for i in idxs:
                e = board.events[i]
                print(f"        └ [{e.time}] {e.source}/{e.etype} {e.raw[:40]}")
    else:
        print("没有案件越过顶出线，系统保持沉睡。")

    deep_reports: list[dict] = []
    if wake:
        print("-" * 64)
        print("【系统2 结构化调查】")
        for cid, idxs in wake:
            chain = [board.events[i] for i in idxs]
            report = system2.deep_analyze_chain(chain, deep_client)
            deep_reports.append({"component": comp_uid[cid], "report": report})
            print(f"\n>>> 案件 {comp_uid[cid]}（{len(idxs)} 条信号）")
            print(f"    定性={report.get('verdict')}  置信度={report.get('confidence')}")
            print(f"    摘要={report.get('digest')}")
            for ioc in report.get("iocs", []):
                print(f"    IOC: {ioc.get('value')}（{ioc.get('context')}）")
            for u in report.get("unknowns", []):
                print(f"    待查: {u}")

    print("-" * 64)
    if learned:
        print(f"本轮学到耐受  : {learned}（下次这几条直接静默，连杏仁核都不用叫）")
    else:
        print("本轮学到耐受  : 0")
    print(f"告警降噪    : {total} 条里 {len(wake)}/{total} 个案件唤醒系统2，"
          f"{len(saved)} 个省下深度算力，{tol_suppressed} 条连杏仁核都没叫。")
    print("夜里跑 `python3 consolidate.py` 巩固记忆；`python3 visualize.py` 生成观测页。")

    _write_last_run(
        knob=knob, path=path,
        counts={
            "total": total, "tol_suppressed": tol_suppressed, "innate_hits": innate_hits,
            "suppressed": suppressed, "surfaced": surfaced,
            "components": len(comp_event_idxs), "escalated": len(escalated),
            "wake": len(wake), "saved": len(saved),
        },
        board=board, comp_uid=event_uid, esc_event_ids=esc_event_ids,
        deep_reports=deep_reports, suppressed_log=suppressed_log, learned=learned,
        system1=type(client).__name__, system2=type(deep_client).__name__,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--knob", default=config.DEFAULT, choices=list(config.PRESETS))
    ap.add_argument("--input", default=None, help="信号文件路径（.jsonl/.json/.csv），默认 data/sample.jsonl")
    args = ap.parse_args()
    run(args.knob, args.input)
