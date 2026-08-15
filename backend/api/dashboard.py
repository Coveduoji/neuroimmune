"""看板 API：省/学/调汇总 + 风险旋钮 + 被抑制审计 + 入库。"""
from __future__ import annotations

import json
from datetime import datetime

import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

import auth
import config
import db
import innate
import pipeline
import report
import signals
import state
import syslog_server
import tolerance
import webhook
from signature import signature
from schemas import KnobSet, IngestRequest

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    tol = tolerance.load_tolerance()
    rules = innate.load_rules()
    knob = state.get_knob(state.get_knob_name())
    return {
        "counts": db.counts(),
        "knob": {"name": knob.name, "suppress_below": knob.suppress_below,
                 "escalate_above": knob.escalate_above, "budget": knob.budget},
        "presets": state.get_all_presets(),
        "tolerance": sorted(tol),
        "innate": sorted(rules),
    }


@router.get("/trend")
def trend(range: str = "24h"):
    """告警流量趋势（时间桶序列）。range: 24h / 7d / 30d。"""
    ranges = {"24h": (24, 3600), "7d": (168, 21600), "30d": (720, 86400)}
    hours, bucket = ranges.get(range, ranges["24h"])
    return {"range": range, "buckets": db.alert_trend(hours, bucket)}


@router.get("/knob")
def get_knob():
    knob = state.get_knob(state.get_knob_name())
    return {"knob": state.get_knob_name(), "suppress_below": knob.suppress_below,
            "escalate_above": knob.escalate_above, "budget": knob.budget}


@router.put("/knob", dependencies=[Depends(auth.require_token)])
def set_knob(body: KnobSet):
    if body.knob not in config.PRESETS:
        return {"error": f"未知档位 {body.knob}"}
    state.set_knob_name(body.knob)
    return get_knob()


@router.get("/suppressed")
def suppressed():
    """被抑制的告警（完整落库，可研判）。"""
    return db.list_suppressed_alerts()


@router.post("/tolerance/remove", dependencies=[Depends(auth.require_token)])
def tolerance_remove(body: dict):
    """从免疫耐受白名单删一条签名。"""
    tol = tolerance.load_tolerance()
    tol.discard((body or {}).get("signature", ""))
    tolerance.save_tolerance(tol)
    return {"remaining": sorted(tol)}


@router.post("/tolerance/clear", dependencies=[Depends(auth.require_token)])
def tolerance_clear():
    tolerance.save_tolerance(set())
    return {"remaining": []}


@router.post("/innate/remove", dependencies=[Depends(auth.require_token)])
def innate_remove(body: dict):
    """从固有免疫规则删一条签名。"""
    rules = innate.load_rules()
    rules.discard((body or {}).get("signature", ""))
    innate.save_rules(rules)
    return {"remaining": sorted(rules)}


@router.post("/innate/clear", dependencies=[Depends(auth.require_token)])
def innate_clear():
    innate.save_rules(set())
    return {"remaining": []}


@router.get("/thalamus")
def list_alerts(source: str | None = None, suppressed: str | None = None, q: str | None = None,
                sort: str = "time", limit: int = 50, offset: int = 0):
    """丘脑（原始告警流）：全部入库告警（含被抑制），支持来源/抑制状态/关键词 + 分页。"""
    items = db.list_all_alerts(source, suppressed, q, sort, limit, offset)
    total = db.count_all_alerts(source, suppressed, q)
    return {"items": items, "total": total, "sources": db.get_distinct_sources()}


@router.get("/audit")
def list_audit(action: str | None = None, limit: int = 200):
    """决策留痕：single_signal_skipped / budget_blocked / 处置等审计日志。"""
    return {"items": db.list_audit(action)[:limit]}


@router.post("/suppressed/{alert_id}/restore", dependencies=[Depends(auth.require_token)])
def restore(alert_id: int):
    """把一条被误压的告警放回：重新上板、归案、触发深度分析。"""
    alert = db.get_alert(alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    signal = {"time": alert["time"], "source": alert["source"], "asset": alert["asset"],
              "type": alert["type"], "raw": alert["raw"]}
    result = pipeline.restore_signal(signal)
    db.delete_alert(alert_id)
    db.insert_audit("restored", f'{alert["asset"]} {alert["type"]}',
                    json.dumps({"from_alert": alert_id}, ensure_ascii=False))
    return result


@router.post("/alerts/{alert_id}/disposition", dependencies=[Depends(auth.require_token)])
def alert_disposition(alert_id: int, body: dict | None = None):
    """对单条告警标记误报/真阳性，回写对应规则（比整案一刀切更细粒度）。"""
    alert = db.get_alert(alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    verdict = (body or {}).get("verdict", "")
    reason = (body or {}).get("reason", "")
    sig = signature(alert["source"], alert["type"], alert["raw"])
    if verdict == "False Positive":
        tol = tolerance.load_tolerance()
        learned = tolerance.learn(tol, [sig])
        if learned:
            tolerance.save_tolerance(tol)
    elif verdict == "True Positive":
        rules = innate.load_rules()
        learned = innate.add(rules, [sig])
        if learned:
            innate.save_rules(rules)
    else:
        raise HTTPException(400, "verdict 必须是 False Positive 或 True Positive")
    db.set_alert_verdict(alert_id, verdict)
    db.append_feedback({
        "type": "false_positive" if verdict == "False Positive" else "true_positive",
        "entities": [[alert["asset"], alert["type"]]],
        "reason": reason,
        "time": datetime.now().isoformat(),
    })
    return {"alert_id": alert_id, "verdict": verdict}


@router.get("/entities/cases")
def entity_cases(type: str, value: str):
    """反查：某个实体出现在哪些案件里。"""
    return db.cases_for_entity(type, value)


@router.get("/hippocampus/events")
def graph_events(type: str, value: str, type2: str | None = None, value2: str | None = None,
                 source: str | None = None, sort: str = "time", limit: int = 200, offset: int = 0):
    """海马体节点/边的关联事件（一次调用拿全量事件，带筛选 + 排序 + 分页）。"""
    if type2 and value2:
        items = db.get_alerts_for_entity_pair(type, value, type2, value2, source, sort, limit, offset)
        total = db.count_alerts_for_entity_pair(type, value, type2, value2, source)
    else:
        items = db.get_alerts_for_entity(type, value, source, sort, limit, offset)
        total = db.count_alerts_for_entity(type, value, source)
    return {"items": items, "total": total, "sources": db.get_distinct_sources()}


@router.get("/hippocampus")
def global_graph():
    """海马体（实体关系图）：所有实体为点、共现为边，点和边都带关联案件。"""
    artifacts = db.get_all_artifacts()
    links = db.get_all_alert_artifacts()
    uid_map = db.get_case_uid_map()

    idx = {a["id"]: i for i, a in enumerate(artifacts)}
    nodes = [{"id": i, "type": a["type"], "value": a["value"], "cases": set(), "degree": 0}
             for i, a in enumerate(artifacts)]

    alert_arts: dict[int, list[int]] = {}
    alert_case: dict[int, int] = {}
    for l in links:
        alert_arts.setdefault(l["alert_id"], []).append(l["artifact_id"])
        alert_case[l["alert_id"]] = l["case_id"]

    edges: dict[tuple[int, int], set[int]] = {}
    for aid, art_ids in alert_arts.items():
        case_id = alert_case[aid]
        for a in art_ids:
            nodes[idx[a]]["cases"].add(case_id)
        for i in range(len(art_ids)):
            for j in range(i + 1, len(art_ids)):
                x, y = sorted((idx[art_ids[i]], idx[art_ids[j]]))
                if x == y:
                    continue
                edges.setdefault((x, y), set()).add(case_id)

    # degree = 唯一邻居数（不是共现次数）
    for x, y in edges:
        nodes[x]["degree"] += 1
        nodes[y]["degree"] += 1

    def _uids(case_ids: set) -> list[str]:
        return [uid_map[c] for c in sorted(case_ids) if c in uid_map]

    return {
        "nodes": [{"id": n["id"], "type": n["type"], "value": n["value"],
                   "cases": _uids(n["cases"]), "degree": n["degree"]} for n in nodes],
        "edges": [{"source": s, "target": t, "cases": _uids(cs)} for (s, t), cs in edges.items()],
    }


@router.post("/ingest", dependencies=[Depends(auth.require_token)])
def ingest(body: IngestRequest):
    """增量入库：不重置，逐条归入/合并案件（24h 流式）。走全局旋钮。"""
    results = [pipeline.process_signal(sig) for sig in body.signals]
    return {"ingested": len(results), "results": results}


@router.post("/reset", dependencies=[Depends(auth.require_token)])
def reset():
    """手动清库（重新开始）。"""
    db.reset()
    return {"status": "reset"}


@router.post("/consolidate", dependencies=[Depends(auth.require_token)])
def consolidate_now():
    """手动触发夜间巩固（睡眠巩固：SQLite → 记忆 + 固有免疫规则）。"""
    import nightly
    return nightly.consolidate()


@router.get("/presets")
def presets():
    return state.get_all_presets()


@router.get("/freq")
def get_freq():
    return state.get_freq_config()


@router.put("/freq", dependencies=[Depends(auth.require_token)])
def set_freq(body: dict):
    cfg = state.get_freq_config()
    state.set_freq_config(
        window=int(body.get("window", cfg["window"])),
        threshold=int(body.get("threshold", cfg["threshold"])),
        demote=float(body.get("demote", cfg["demote"])),
    )
    return state.get_freq_config()


@router.get("/mode")
def get_mode():
    return {"mode": state.get_model_mode()}


@router.put("/mode", dependencies=[Depends(auth.require_token)])
def set_mode(body: dict):
    mode = (body or {}).get("mode", "")
    if mode not in ("auto", "mock", "real"):
        raise HTTPException(400, f"未知模式 {mode}")
    state.set_model_mode(mode)
    return {"mode": state.get_model_mode()}


@router.get("/gating")
def get_gating():
    return state.get_gating_config()


@router.put("/gating", dependencies=[Depends(auth.require_token)])
def set_gating(body: dict):
    cfg = state.get_gating_config()
    state.set_gating_config(
        single_signal_floor=float(body.get("single_signal_floor", cfg["single_signal_floor"])),
        budget_window=int(body.get("budget_window", cfg["budget_window"])),
    )
    return state.get_gating_config()


def _mask(key: str) -> str:
    if not key:
        return ""
    return f"••••{key[-4:]}" if len(key) > 4 else "••••"


@router.get("/model")
def get_model():
    m = state.get_model_config()
    return {**m, "api_key": _mask(m["api_key"]), "deep_api_key": _mask(m["deep_api_key"])}


@router.put("/model", dependencies=[Depends(auth.require_token)])
def set_model(body: dict):
    m = state.get_model_config()
    # key 掩码或空 = 不覆盖；给新值才更新
    if body.get("api_key") and not str(body["api_key"]).startswith("••••"):
        m["api_key"] = body["api_key"]
    if body.get("deep_api_key") and not str(body["deep_api_key"]).startswith("••••"):
        m["deep_api_key"] = body["deep_api_key"]
    for k in ("base_url", "model", "deep_base_url", "deep_model", "temperature", "timeout"):
        if k in body and body[k] is not None:
            m[k] = body[k]
    m = state.set_model_config(m)
    return {**m, "api_key": _mask(m["api_key"]), "deep_api_key": _mask(m["deep_api_key"])}


@router.get("/detection")
def get_detection():
    return state.get_detection_config()


@router.put("/detection", dependencies=[Depends(auth.require_token)])
def set_detection(body: dict):
    return state.set_detection_config(body)


@router.get("/ingest")
def get_ingest():
    ing = state.get_ingest_config()
    return {**ing, "api_token": _mask(ing["api_token"])}


@router.put("/ingest", dependencies=[Depends(auth.require_token)])
def set_ingest(body: dict):
    ing = state.get_ingest_config()
    if body.get("api_token") and not str(body["api_token"]).startswith("••••"):
        ing["api_token"] = body["api_token"]
    for k in ("syslog_bind", "syslog_port", "consolidate_interval"):
        if k in body and body[k] is not None:
            ing[k] = body[k]
    ing = state.set_ingest_config(ing)
    return {**ing, "api_token": _mask(ing["api_token"])}


@router.get("/sources")
def get_sources():
    return state.get_sources_config()


@router.put("/sources", dependencies=[Depends(auth.require_token)])
def set_sources(body: dict):
    return state.set_sources_config(body)


@router.post("/report/export")
def export_report(body: dict):
    """按筛选条件导出报告（docx / md / html）。body: {format, start, end, source, verdict, status}。"""
    body = body or {}
    fmt = body.get("format", "html")
    filters = {k: v for k, v in body.items() if k != "format" and v not in ("", None)}
    try:
        media, ext, content = report.export_report(filters, fmt)
    except ValueError as e:
        raise HTTPException(400, str(e))
    filename = f"neuroimmune-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/webhooks")
def list_webhooks():
    return {"items": webhook.load_webhooks()}


@router.post("/webhooks", dependencies=[Depends(auth.require_token)])
def add_webhook(body: dict):
    wbs = webhook.load_webhooks()
    wbs.append({
        "name": (body or {}).get("name", "webhook"),
        "url": (body or {}).get("url", ""),
        "token": (body or {}).get("token", ""),
        "trigger": (body or {}).get("trigger", "escalated"),
        "enabled": (body or {}).get("enabled", True),
        "fields": (body or {}).get("fields", webhook.ALL_FIELDS),
    })
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.put("/webhooks/{index}", dependencies=[Depends(auth.require_token)])
def update_webhook(index: int, body: dict):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    for k in ("name", "url", "token", "trigger", "enabled", "fields"):
        if k in (body or {}):
            wbs[index][k] = body[k]
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.delete("/webhooks/{index}", dependencies=[Depends(auth.require_token)])
def delete_webhook(index: int):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    wbs.pop(index)
    webhook.save_webhooks(wbs)
    return {"items": wbs}


@router.post("/webhooks/{index}/test", dependencies=[Depends(auth.require_token)])
def test_webhook(index: int):
    wbs = webhook.load_webhooks()
    if not (0 <= index < len(wbs)):
        raise HTTPException(404, "webhook 不存在")
    return {"ok": webhook.test_webhook(wbs[index])}


@router.put("/presets/{name}", dependencies=[Depends(auth.require_token)])
def update_preset(name: str, body: dict):
    if name not in config.PRESETS:
        raise HTTPException(404, f"未知档位 {name}")
    state.set_preset(
        name,
        suppress_below=float(body.get("suppress_below", 0.55)),
        escalate_above=float(body.get("escalate_above", 0.75)),
        budget=int(body.get("budget", 2)),
    )
    return state.get_all_presets()


@router.get("/info")
def info():
    import llm
    llm.load_dotenv()  # 保证 env fallback 可读
    m = state.get_model_config()
    ing = state.get_ingest_config()
    return {
        "syslog": {"bind": ing["syslog_bind"], "port": int(ing["syslog_port"])},
        "model": m["model"] or os.environ.get("NEUROIMMUNE_MODEL", "deepseek-chat"),
        "deep_model": m["deep_model"] or os.environ.get("NEUROIMMUNE_DEEP_MODEL", "deepseek-reasoner"),
        "mode": state.get_model_mode(),
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
        "db": db.counts(),
        "syslog": {"listening": syslog_server.listening, "last_ingest": syslog_server.last_ingest},
        "knob": state.get_knob_name(),
        "mode": state.get_model_mode(),
    }


@router.post("/ingest/upload", dependencies=[Depends(auth.require_token)])
async def ingest_upload(file: UploadFile = File(...)):
    """上传 JSONL/JSON/CSV 文件，增量入库。"""
    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1].lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="wb") as f:
        f.write(content)
        tmp = f.name
    try:
        sigs = signals.load_signals(tmp)
    finally:
        os.unlink(tmp)
    results = [pipeline.process_signal(s) for s in sigs]
    return {"ingested": len(results), "results": results}
