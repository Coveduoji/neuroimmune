"""管道服务——复用 prototype 的核心判断逻辑，把信号 → 案件/报告 → 落库。

核心判断（杏仁核 / 实体 / 图 / 系统2）一行不改，只把 main.py 的批处理逻辑
抽成可复用函数，产出落进 SQLite。
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

import amygdala
import artifact
import blackboard
import config
import graph as graphmod
import innate
import system2
import tolerance

import db
import state
import webhook


# ---- 系统2 唤醒预算（滑动窗口计数）----
# prototype/receiver.py 是「每 window 秒收集候选、取前 budget 个唤醒」，但 Web 后端的
# process_signal 是持续流式（syslog + HTTP 上传），没有天然窗口。这里用滑动窗口计数：
# 最近 window 秒内，最多 budget 个「不同案件」唤醒系统2；同一案件随告警
# 增长（grew>=2）的重分析不计入新预算——它还是那一个案件，只是补全证据。进程内共享，重启归零。
# window / 单信号地板值都从 state.get_gating_config() 读，设置页可调。
_woken_cases: dict[int, float] = {}  # case_id -> 最近一次唤醒时间
_wake_lock = threading.Lock()


def _within_budget(budget: int, window: int) -> bool:
    """当前是否还能唤醒系统2：窗口内已唤醒的不同案件数 < budget。"""
    cutoff = time.time() - window
    with _wake_lock:
        for cid in [c for c, t in _woken_cases.items() if t <= cutoff]:
            _woken_cases.pop(cid, None)
        return len(_woken_cases) < budget


def _record_wake(case_id: int) -> None:
    with _wake_lock:
        _woken_cases[case_id] = time.time()


# 同一案件随告警增长会触发多次重分析（grew>=2）。并发跑会竞态：早启动的（证据少）
# 可能后写完、覆盖晚启动的（证据全）。用 per-case 锁串行化：后启动的排队，最后写完的
# 是证据最全的那份报告。
_case_locks: dict[int, threading.Lock] = {}
_case_locks_guard = threading.Lock()


def _case_lock(case_id: int) -> threading.Lock:
    with _case_locks_guard:
        return _case_locks.setdefault(case_id, threading.Lock())


def _run_system2(case_id: int, events, deep_client, knowledge) -> None:
    """后台跑系统2，per-case 串行，不阻塞入库。"""
    with _case_lock(case_id):
        db.insert_report(case_id, system2.deep_analyze_chain(events, deep_client, knowledge))
    webhook.notify("escalated", case_id)  # 深析报告就绪后外发


def process(signals: list[dict], knob_name: str = "正常") -> dict:
    db.init_db()
    knob = state.get_knob(knob_name)
    d = state.get_detection_config()
    client = state.get_client()
    deep_client = state.get_deep_client()
    tol = tolerance.load_tolerance()
    rules = innate.load_rules()

    events: list[blackboard.Event] = []
    suppressed: list[dict] = []
    total = innate_hits = tol_suppressed = suppressed_n = 0

    for sig in signals:
        total += 1
        if tolerance.is_tolerated(sig, tol):
            tol_suppressed += 1
            suppressed.append({**sig, "confidence": None, "why": "免疫耐受：已知好，白名单降级"})
            continue
        if innate.match(sig, rules):
            innate_hits += 1
            events.append(blackboard.Event(
                time=sig["time"], source=sig["source"], asset=sig["asset"], etype=sig["type"],
                confidence=d["innate_conf"], raw=sig["raw"], reason="固有免疫秒拦：已知攻击家族", innate=True,
            ))
            continue
        v = amygdala.judge_signal(sig, client)
        if v.confidence < knob.suppress_below:
            suppressed_n += 1
            suppressed.append({**sig, "confidence": round(v.confidence, 2),
                               "why": f"杏仁核低置信度（{v.confidence:.2f} < {knob.suppress_below}）"})
            continue
        events.append(blackboard.Event(
            time=sig["time"], source=sig["source"], asset=sig["asset"], etype=sig["type"],
            confidence=v.confidence, raw=sig["raw"], reason=v.reason,
        ))

    # 建图 → 连通分量归案
    g = graphmod.Graph()
    for i, e in enumerate(events):
        ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})
        if ents:
            g.add_signal(i, ents)
    sig_comp = graphmod.signal_components(g)
    comps = g.components()

    comp_event_idxs: dict[int, list[int]] = {}
    for i, cid in enumerate(sig_comp):
        if cid >= 0:
            comp_event_idxs.setdefault(cid, []).append(i)

    def strength(idxs: list[int]) -> float:
        confs = [events[i].confidence for i in idxs]
        return max(confs) + min(d["chain_cap"], d["chain_bonus"] * (len(idxs) - 1))

    ranked = sorted(comp_event_idxs.items(), key=lambda kv: strength(kv[1]), reverse=True)
    escalated_cids = {cid for cid, idxs in ranked if strength(idxs) >= knob.escalate_above}

    # 落库
    case_summaries = []
    for cid, idxs in comp_event_idxs.items():
        ents = [g.entities[i] for i in comps[cid]]
        uid = graphmod.component_id(ents)
        title = "、".join(f"{e.value}" for e in ents[:3]) or "未命名案件"
        case_id = db.insert_case(
            correlation_uid=uid, title=title, strength=round(strength(idxs), 3),
            entity_summary=json.dumps([{"type": e.type, "value": e.value} for e in ents], ensure_ascii=False),
        )
        for i in idxs:
            e = events[i]
            alert_id = db.insert_alert(case_id, e)
            for ent in artifact.extract_entities({"asset": e.asset, "raw": e.raw}):
                db.link_alert_artifact(alert_id, db.get_or_create_artifact(ent.type, ent.value))
        # 顶出且含非固有免疫事件 → 系统2 结构化调查（带记忆 RAG）
        if cid in escalated_cids and any(not events[i].innate for i in idxs):
            knowledge = _retrieve_knowledge([g.entities[i].value for i in comps[cid]], d["rag_limit"])
            report = system2.deep_analyze_chain([events[i] for i in idxs], deep_client, knowledge)
            db.insert_report(case_id, report)
            webhook.notify("escalated", case_id)
        case_summaries.append({
            "id": case_id, "correlation_uid": uid, "strength": round(strength(idxs), 3),
            "alerts": len(idxs), "escalated": cid in escalated_cids,
        })

    # 被抑制信号完整落库（suppressed=1，支持「放回」研判），与增量 process_signal 一致。
    # 不再写 audit「suppressed」噪声——被抑制信号本就该在 alerts 表里，audit 留给决策事件。
    for s in suppressed:
        sig = {k: v for k, v in s.items() if k != "why"}
        db.insert_suppressed_alert(sig, s.get("why", ""))

    return {
        "counts": {
            "total": total, "tol_suppressed": tol_suppressed, "innate_hits": innate_hits,
            "suppressed": suppressed_n, "surfaced": len(events),
            "components": len(comp_event_idxs), "escalated": len(escalated_cids),
        },
        "cases": case_summaries,
    }


def _alert_to_event(a: dict) -> blackboard.Event:
    return blackboard.Event(
        time=a["time"], source=a["source"], asset=a["asset"], etype=a["type"],
        confidence=a["confidence"], raw=a["raw"], reason=a["reason"], innate=bool(a["innate"]),
    )


def _retrieve_knowledge(entity_values: list[str], limit: int = 5) -> list[str]:
    """记忆 RAG：按实体值检索过去的误报经验和历史记忆。"""
    knowledge = []
    for rec in db.get_feedback():
        vals = {e[0] for e in rec.get("entities", []) if isinstance(e, list) and e}
        if any(v in vals for v in entity_values):
            label = "真阳性经验" if rec.get("type") == "true_positive" else "误报经验"
            knowledge.append(f"{label}（{rec.get('case_uid', '')[:8]}）：{rec.get('reason', '')}")
    for rec in db.get_memory():
        text = rec.get("summary", "")
        if text and any(v in text for v in entity_values):
            knowledge.append(f"历史记忆：{text}")
    return knowledge[-limit:]


def process_signal(signal: dict, knob_name: str | None = None) -> dict:
    """增量处理一条信号：过管道 → 按实体归入/合并案件 → 首次顶出才系统2。

    这是 24h 流式入库的核心：不重置、不跑全量，每条信号用 correlation_uid 的实体
    反查已有案件，归入或合并，案件强度动态累加。knob_name 为空时用全局旋钮。
    """
    db.init_db()
    knob = state.get_knob(knob_name or state.get_knob_name())
    d = state.get_detection_config()
    gating = state.get_gating_config()
    client = state.get_client()
    deep_client = state.get_deep_client()
    tol = tolerance.load_tolerance()
    rules = innate.load_rules()

    def _suppress(why: str, confidence=None) -> dict:
        db.insert_suppressed_alert({**signal, "confidence": confidence}, why)
        return {"status": "suppressed", "why": why}

    if tolerance.is_tolerated(signal, tol):
        return _suppress("免疫耐受：已知好，白名单降级")

    if innate.match(signal, rules):
        e = blackboard.Event(
            time=signal["time"], source=signal["source"], asset=signal["asset"], etype=signal["type"],
            confidence=d["innate_conf"], raw=signal["raw"], reason="固有免疫秒拦：已知攻击家族", innate=True,
        )
    else:
        v = amygdala.judge_signal(signal, client)
        # 频率降级：时间窗外历史同类型告警极多 → 很可能业务误报，降级并写记忆
        freq = state.get_freq_config()
        hist = db.count_historical_alerts(signal["asset"], signal["type"], freq["window"])
        freq_demoted = False
        if hist >= freq["threshold"]:
            v = amygdala.Verdict(
                v.suspicious, round(v.confidence * freq["demote"], 2),
                f"{v.reason}（历史同类型告警 {hist} 次，疑似业务误报）",
            )
            freq_demoted = True
            db.append_feedback({
                "type": "frequency_false_positive",
                "asset": signal["asset"], "signal_type": signal["type"],
                "count": hist, "time": datetime.now().isoformat(),
            })
        if v.confidence < knob.suppress_below:
            why = (f"频率降级：历史同类型告警 {hist} 次，疑似业务误报"
                   if freq_demoted else
                   f"杏仁核低置信度（{v.confidence:.2f} < {knob.suppress_below}）")
            return _suppress(why, confidence=v.confidence)
        e = blackboard.Event(
            time=signal["time"], source=signal["source"], asset=signal["asset"], etype=signal["type"],
            confidence=v.confidence, raw=signal["raw"], reason=v.reason,
        )

    ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})

    # 归案：任一实体命中的已有案件
    case_ids: set[int] = set()
    for ent in ents:
        for c in db.cases_for_entity(ent.type, ent.value):
            case_ids.add(c["id"])

    if len(case_ids) > 1:
        keep = min(case_ids)
        for cid in sorted(case_ids - {keep}):
            db.merge_case(cid, keep)
        case_id = keep
    elif len(case_ids) == 1:
        case_id = case_ids.pop()
    else:
        uid = graphmod.component_id(ents)
        title = "、".join(x.value for x in ents[:3]) or "未命名案件"
        case_id = db.insert_case(
            correlation_uid=uid, title=title, strength=0.0,
            entity_summary=json.dumps([{"type": x.type, "value": x.value} for x in ents], ensure_ascii=False),
        )

    alert_id = db.insert_alert(case_id, e)
    for ent in ents:
        db.link_alert_artifact(alert_id, db.get_or_create_artifact(ent.type, ent.value))

    # 更新案件强度
    alerts = db.get_case_alerts(case_id)
    strength = max(a["confidence"] for a in alerts) + min(d["chain_cap"], d["chain_bonus"] * (len(alerts) - 1))
    db.update_case_strength(case_id, round(strength, 3))

    # 顶出决策：越过顶出线才考虑唤醒系统2，但要过两重门——
    #   ① 单信号门槛：单信号案件默认不醒（除非 conf >= 地板值），要等拼链或确凿单点 IOC；
    #   ② 预算门：滑动窗口内最多 knob.budget 个不同案件唤醒。
    # 被门拦下的也写审计——「抑制不是静默，全程可审计」。
    if strength >= knob.escalate_above:
        max_conf = max(a["confidence"] for a in alerts)
        worthy = len(alerts) >= 2 or max_conf >= gating["single_signal_floor"]
        report_exists = db.get_case_report(case_id) is not None
        grew = len(alerts) - (db.get_case(case_id).get("reported_at_alerts") or 0) >= d["grew"]
        if worthy and (not report_exists or grew):
            if _within_budget(knob.budget, gating["budget_window"]):
                _record_wake(case_id)
                events = [_alert_to_event(a) for a in alerts]
                knowledge = _retrieve_knowledge([x.value for x in ents], d["rag_limit"])
                db.set_case_reported_alerts(case_id, len(alerts))
                threading.Thread(
                    target=_run_system2, args=(case_id, events, deep_client, knowledge),
                    daemon=True,
                ).start()
            else:
                db.insert_audit("budget_blocked", f"case {case_id}",
                                json.dumps({"strength": round(strength, 3), "alerts": len(alerts),
                                            "budget": knob.budget}, ensure_ascii=False))
        elif not worthy:
            db.insert_audit("single_signal_skipped", f"case {case_id}",
                            json.dumps({"max_conf": max_conf, "alerts": len(alerts),
                                        "floor": gating["single_signal_floor"]}, ensure_ascii=False))

    return {"status": "ingested", "case_id": case_id, "strength": round(strength, 3), "alerts": len(alerts)}


def restore_signal(signal: dict) -> dict:
    """分析师放回一条被误压的信号：强制上板、归入案件、触发系统2 深想。"""
    db.init_db()
    d = state.get_detection_config()
    deep_client = state.get_deep_client()
    e = blackboard.Event(
        time=signal.get("time", ""), source=signal.get("source", ""), asset=signal.get("asset", ""),
        etype=signal.get("type", ""), confidence=d["restore_conf"], raw=signal.get("raw", ""),
        reason="分析师放回：被误压的信号",
    )
    ents = artifact.extract_entities({"asset": e.asset, "raw": e.raw})
    uid = graphmod.component_id(ents)
    existing = db.get_case_by_uid(uid)
    if existing:
        case_id = existing["id"]
    else:
        title = "、".join(f"{x.value}" for x in ents[:3]) or "放回信号"
        case_id = db.insert_case(
            correlation_uid=uid, title=title, strength=d["restore_conf"],
            entity_summary=json.dumps([{"type": x.type, "value": x.value} for x in ents], ensure_ascii=False),
        )
    alert_id = db.insert_alert(case_id, e)
    for ent in ents:
        db.link_alert_artifact(alert_id, db.get_or_create_artifact(ent.type, ent.value))
    # 后台跑系统2，放回立即返回、不阻塞，带记忆 RAG
    import threading
    knowledge = _retrieve_knowledge([x.value for x in ents], d["rag_limit"])
    threading.Thread(
        target=lambda: db.insert_report(case_id, system2.deep_analyze_chain([e], deep_client, knowledge)),
        daemon=True,
    ).start()
    return {"case_id": case_id, "correlation_uid": uid}
