"""SQLite 数据层（零 ORM 依赖，用标准库 sqlite3）。

表：alerts / artifacts / alert_artifacts / cases / reports / audit_logs。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from paths import DB_PATH, FEEDBACK_PATH, MEMORY_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    time TEXT, source TEXT, asset TEXT, type TEXT, raw TEXT,
    confidence REAL, reason TEXT, innate INTEGER DEFAULT 0, label TEXT DEFAULT '',
    suppressed INTEGER DEFAULT 0, why TEXT DEFAULT '', verdict TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT, value TEXT, UNIQUE(type, value)
);
CREATE TABLE IF NOT EXISTS alert_artifacts (
    alert_id INTEGER, artifact_id INTEGER
);
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_uid TEXT UNIQUE,
    title TEXT, strength REAL,
    status TEXT DEFAULT 'New', verdict TEXT DEFAULT '', severity TEXT DEFAULT '',
    entity_summary TEXT DEFAULT '[]',
    disposition_note TEXT DEFAULT '',
    reported_at_alerts INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER UNIQUE,
    verdict TEXT, confidence TEXT, digest TEXT,
    evidence_json TEXT, iocs_json TEXT, unknowns_json TEXT, remediations_json TEXT, attack_chain_json TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT, entity TEXT, changes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT DEFAULT 'user',
    permissions TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# 高频路径索引：避免 count_historical_alerts 全表扫描、实体反查 JOIN 随数据量变慢
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_alerts_asset_type_created ON alerts(asset, type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_case_id ON alerts(case_id)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(source)",
    "CREATE INDEX IF NOT EXISTS idx_alert_artifacts_alert_id ON alert_artifacts(alert_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_artifacts_artifact_id ON alert_artifacts(artifact_id)",
)

# init_db 幂等化：建库/迁移/索引只在首次执行，热路径每条信号调到的 init_db 直接返回
_init_lock = threading.Lock()
_initialized = False


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        # WAL 需在无事务的独立连接上设置，持久化到 DB 文件头；读写并发不再互斥
        _wal = _conn()
        try:
            _wal.execute("PRAGMA journal_mode=WAL")
        finally:
            _wal.close()
        with _conn() as c:
            c.executescript(SCHEMA)
            # 迁移：老库的 reports 表可能缺 attack_chain_json 列
            cols = [r[1] for r in c.execute("PRAGMA table_info(reports)").fetchall()]
            if "attack_chain_json" not in cols:
                c.execute("ALTER TABLE reports ADD COLUMN attack_chain_json TEXT")
            # 迁移：老库的 cases 表可能缺 disposition_note 列
            cols = [r[1] for r in c.execute("PRAGMA table_info(cases)").fetchall()]
            if "disposition_note" not in cols:
                c.execute("ALTER TABLE cases ADD COLUMN disposition_note TEXT DEFAULT ''")
            # 迁移：老库的 alerts 表可能缺 suppressed / why / verdict 列
            cols = [r[1] for r in c.execute("PRAGMA table_info(alerts)").fetchall()]
            if "suppressed" not in cols:
                c.execute("ALTER TABLE alerts ADD COLUMN suppressed INTEGER DEFAULT 0")
            if "why" not in cols:
                c.execute("ALTER TABLE alerts ADD COLUMN why TEXT DEFAULT ''")
            if "verdict" not in cols:
                c.execute("ALTER TABLE alerts ADD COLUMN verdict TEXT DEFAULT ''")
            if "created_at" not in cols:
                c.execute("ALTER TABLE alerts ADD COLUMN created_at TEXT DEFAULT ''")
            # 迁移：老库的 cases 表可能缺 reported_at_alerts 列
            cols = [r[1] for r in c.execute("PRAGMA table_info(cases)").fetchall()]
            if "reported_at_alerts" not in cols:
                c.execute("ALTER TABLE cases ADD COLUMN reported_at_alerts INTEGER DEFAULT 0")
            # 迁移：老库的 users 表可能缺 permissions 列
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
            if "permissions" not in cols:
                c.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '[]'")
            # 高频路径索引（幂等；在已有数据的旧库上首次会一次性重建）
            for ddl in INDEXES:
                c.execute(ddl)
        _initialized = True


# ---- 用户 ----

def _user_row(d: dict) -> dict:
    d["permissions"] = json.loads(d.get("permissions") or "[]")
    return d


def create_user(username: str, password_hash: str, role: str = "user",
                permissions: list[str] | None = None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, permissions) VALUES (?,?,?,?)",
            (username, password_hash, role, json.dumps(permissions or [], ensure_ascii=False)),
        )
        return cur.lastrowid


def get_user(user_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _user_row(dict(r)) if r else None


def get_user_by_username(username: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return _user_row(dict(r)) if r else None


def list_users() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT id, username, role, permissions, created_at FROM users ORDER BY id").fetchall()
        return [_user_row(dict(r)) for r in rows]


def delete_user(user_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (user_id,))


def update_user_password(user_id: int, password_hash: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))


def update_user(user_id: int, changes: dict) -> None:
    sets = ", ".join(f"{k}=?" for k in changes)
    with _conn() as c:
        c.execute(f"UPDATE users SET {sets} WHERE id=?", (*changes.values(), user_id))


def count_admins() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]


def append_feedback(record: dict) -> None:
    """处置理由作为学习素材：追加到 feedback.jsonl，供未来调查检索（RAG）。"""
    p = FEEDBACK_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_feedback() -> list[dict]:
    """读全部处置反馈（误报经验）。"""
    p = FEEDBACK_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def get_memory() -> list[dict]:
    """读睡眠巩固沉淀的历史记忆（data_dir()/data/memory.jsonl）。"""
    p = MEMORY_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def reset() -> None:
    """清空所有表（MVP：ingest 前重置，连续入库留 P2）。"""
    with _conn() as c:
        for t in ("alerts", "artifacts", "alert_artifacts", "cases", "reports", "audit_logs"):
            c.execute(f"DELETE FROM {t}")


def insert_case(correlation_uid: str, title: str, strength: float, entity_summary: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO cases (correlation_uid, title, strength, entity_summary) VALUES (?,?,?,?)",
            (correlation_uid, title, strength, entity_summary),
        )
        return cur.lastrowid


def insert_alert(case_id: int, e) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO alerts (case_id, time, source, asset, type, raw, confidence, reason, innate, label, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))",
            (case_id, e.time, e.source, e.asset, e.etype, e.raw, e.confidence, e.reason,
             int(e.innate), e.label),
        )
        return cur.lastrowid


def insert_suppressed_alert(signal: dict, why: str) -> int:
    """被抑制的告警也完整落库（suppressed=1，不关联案件），保证 AI 放过的告警可研判。"""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO alerts (case_id, time, source, asset, type, raw, confidence, reason, suppressed, why, created_at) "
            "VALUES (NULL,?,?,?,?,?,?,?,1,?, datetime('now'))",
            (signal.get("time", ""), signal.get("source", ""), signal.get("asset", ""),
             signal.get("type", ""), signal.get("raw", ""), signal.get("confidence"), "", why),
        )
        return cur.lastrowid


def list_suppressed_alerts(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM alerts WHERE suppressed=1 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def count_historical_alerts(asset: str, type_: str, window_seconds: int) -> int:
    """统计时间窗外（更早于 window_seconds）同 (asset, type) 的历史告警数。

    用于频率降级：历史上同类型告警极多 → 很可能是业务误报。
    """
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM alerts WHERE asset=? AND type=? AND created_at < datetime('now', ?)",
            (asset, type_, f"-{window_seconds} seconds"),
        ).fetchone()[0]


def get_alert(alert_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        return dict(r) if r else None


def delete_alert(alert_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM alerts WHERE id=?", (alert_id,))


def get_or_create_artifact(type_: str, value: str) -> int:
    """幂等取/建实体：INSERT OR IGNORE 消除并发下的 SELECT-then-INSERT 竞态（撞 UNIQUE）。"""
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO artifacts (type, value) VALUES (?,?)", (type_, value))
        row = c.execute("SELECT id FROM artifacts WHERE type=? AND value=?", (type_, value)).fetchone()
        return row["id"]


def link_alert_artifact(alert_id: int, artifact_id: int) -> None:
    with _conn() as c:
        c.execute("INSERT INTO alert_artifacts (alert_id, artifact_id) VALUES (?,?)", (alert_id, artifact_id))


def insert_report(case_id: int, report: dict) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO reports (case_id, verdict, confidence, digest, evidence_json, iocs_json, unknowns_json, remediations_json, attack_chain_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (case_id, report.get("verdict", ""), report.get("confidence", ""), report.get("digest", ""),
             json.dumps(report.get("evidence", []), ensure_ascii=False),
             json.dumps(report.get("iocs", []), ensure_ascii=False),
             json.dumps(report.get("unknowns", []), ensure_ascii=False),
             json.dumps(report.get("remediations", []), ensure_ascii=False),
             json.dumps(report.get("attack_chain", []), ensure_ascii=False)),
        )


def insert_audit(action: str, entity: str, changes: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO audit_logs (action, entity, changes) VALUES (?,?,?)", (action, entity, changes))


# ---- 查询 ----

def _case_filter(status=None, verdict=None, severity=None, pending=False):
    q = " WHERE 1=1"
    args = []
    if status:
        q += " AND status=?"
        args.append(status)
    if pending:
        q += " AND status IN ('New','In Progress','On Hold')"
    if verdict:
        q += " AND verdict=?"
        args.append(verdict)
    if severity:
        q += " AND severity=?"
        args.append(severity)
    return q, args


def list_cases(status=None, verdict=None, severity=None, pending=False, limit=50, offset=0) -> list[dict]:
    fq, args = _case_filter(status, verdict, severity, pending)
    q = f"SELECT * FROM cases{fq} ORDER BY strength DESC, id DESC LIMIT ? OFFSET ?"
    with _conn() as c:
        rows = c.execute(q, args + [limit, offset]).fetchall()
        return [_case_row(r) for r in rows]


def count_cases(status=None, verdict=None, severity=None, pending=False) -> int:
    fq, args = _case_filter(status, verdict, severity, pending)
    with _conn() as c:
        return c.execute(f"SELECT COUNT(*) AS c FROM cases{fq}", args).fetchone()["c"]


def _case_row(r) -> dict:
    d = dict(r)
    d["entities"] = json.loads(d.pop("entity_summary", "[]") or "[]")
    return d


def get_case(case_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return _case_row(r) if r else None


def get_case_alerts(case_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM alerts WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
        return [dict(r) for r in rows]


def get_alert_artifacts(alert_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT a.type, a.value FROM artifacts a JOIN alert_artifacts aa ON a.id=aa.artifact_id "
            "WHERE aa.alert_id=?", (alert_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_case_report(case_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM reports WHERE case_id=?", (case_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        for k in ("evidence_json", "iocs_json", "unknowns_json", "remediations_json", "attack_chain_json"):
            d[k[:-5]] = json.loads(d.pop(k, "[]") or "[]")
        return d


def get_case_by_uid(uid: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM cases WHERE correlation_uid=?", (uid,)).fetchone()
        return _case_row(r) if r else None


def cases_for_entity(type_: str, value: str) -> list[dict]:
    """反查：某个实体出现在哪些案件里（跨案件关联）。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT c.* FROM cases c "
            "JOIN alerts a ON a.case_id = c.id "
            "JOIN alert_artifacts aa ON aa.alert_id = a.id "
            "JOIN artifacts ar ON ar.id = aa.artifact_id "
            "WHERE ar.type=? AND ar.value=? ORDER BY c.strength DESC",
            (type_, value),
        ).fetchall()
        return [_case_row(r) for r in rows]


def get_audit(audit_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM audit_logs WHERE id=?", (audit_id,)).fetchone()
        return dict(r) if r else None


def get_all_artifacts() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT id, type, value FROM artifacts").fetchall()]


def get_all_alert_artifacts() -> list[dict]:
    """所有 (alert_id, case_id, artifact_id) 三元组，供海马体（实体关系图）建边。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT aa.alert_id, a.case_id, aa.artifact_id FROM alert_artifacts aa "
            "JOIN alerts a ON a.id = aa.alert_id",
        ).fetchall()
        return [dict(r) for r in rows]


def get_case_uid_map() -> dict[int, str]:
    with _conn() as c:
        rows = c.execute("SELECT id, correlation_uid FROM cases").fetchall()
        return {r["id"]: r["correlation_uid"] for r in rows}


def get_distinct_sources() -> list[str]:
    with _conn() as c:
        return [r["source"] for r in c.execute("SELECT DISTINCT source FROM alerts WHERE source != ''").fetchall()]


def _alert_where(source: str | None):
    q = ""
    args = []
    if source:
        q += " AND a.source=?"
        args.append(source)
    return q, args


def _order_by(sort: str) -> str:
    # sort=time → 按到达顺序（id）倒序；sort=confidence → 按置信度倒序
    return "a.confidence DESC" if sort == "confidence" else "a.id DESC"


def get_alerts_for_entity(type_, value, source=None, sort="time", limit=200, offset=0):
    wq, args = _alert_where(source)
    order = _order_by(sort)
    q = (f"SELECT DISTINCT a.*, c.correlation_uid AS case_uid, c.id AS case_id FROM alerts a "
         f"JOIN alert_artifacts aa ON aa.alert_id = a.id "
         f"JOIN artifacts ar ON ar.id = aa.artifact_id "
         f"JOIN cases c ON c.id = a.case_id "
         f"WHERE ar.type=? AND ar.value=?{wq} ORDER BY {order} LIMIT ? OFFSET ?")
    with _conn() as c:
        return [dict(r) for r in c.execute(q, [type_, value] + args + [limit, offset]).fetchall()]


def count_alerts_for_entity(type_, value, source=None) -> int:
    wq, args = _alert_where(source)
    q = (f"SELECT COUNT(DISTINCT a.id) AS c FROM alerts a "
         f"JOIN alert_artifacts aa ON aa.alert_id = a.id "
         f"JOIN artifacts ar ON ar.id = aa.artifact_id "
         f"WHERE ar.type=? AND ar.value=?{wq}")
    with _conn() as c:
        return c.execute(q, [type_, value] + args).fetchone()["c"]


def get_alerts_for_entity_pair(type1, value1, type2, value2, source=None, sort="time", limit=200, offset=0):
    wq, args = _alert_where(source)
    order = _order_by(sort)
    q = (f"SELECT DISTINCT a.*, c.correlation_uid AS case_uid, c.id AS case_id FROM alerts a "
         f"JOIN alert_artifacts aa1 ON aa1.alert_id = a.id "
         f"JOIN artifacts ar1 ON ar1.id = aa1.artifact_id "
         f"JOIN alert_artifacts aa2 ON aa2.alert_id = a.id "
         f"JOIN artifacts ar2 ON ar2.id = aa2.artifact_id "
         f"JOIN cases c ON c.id = a.case_id "
         f"WHERE ar1.type=? AND ar1.value=? AND ar2.type=? AND ar2.value=?{wq} ORDER BY {order} LIMIT ? OFFSET ?")
    with _conn() as c:
        return [dict(r) for r in c.execute(q, [type1, value1, type2, value2] + args + [limit, offset]).fetchall()]


def count_alerts_for_entity_pair(type1, value1, type2, value2, source=None) -> int:
    wq, args = _alert_where(source)
    q = (f"SELECT COUNT(DISTINCT a.id) AS c FROM alerts a "
         f"JOIN alert_artifacts aa1 ON aa1.alert_id = a.id "
         f"JOIN artifacts ar1 ON ar1.id = aa1.artifact_id "
         f"JOIN alert_artifacts aa2 ON aa2.alert_id = a.id "
         f"JOIN artifacts ar2 ON ar2.id = aa2.artifact_id "
         f"WHERE ar1.type=? AND ar1.value=? AND ar2.type=? AND ar2.value=?{wq}")
    with _conn() as c:
        return c.execute(q, [type1, value1, type2, value2] + args).fetchone()["c"]


def patch_case(case_id: int, changes: dict) -> None:
    sets = ", ".join(f"{k}=?" for k in changes)
    with _conn() as c:
        c.execute(f"UPDATE cases SET {sets} WHERE id=?", (*changes.values(), case_id))


def update_case_strength(case_id: int, strength: float) -> None:
    with _conn() as c:
        c.execute("UPDATE cases SET strength=? WHERE id=?", (strength, case_id))


def merge_case(from_id: int, to_id: int) -> None:
    """把一个案件并进另一个：re-point 告警，删掉被并的案件和它的报告。"""
    with _conn() as c:
        c.execute("UPDATE alerts SET case_id=? WHERE case_id=?", (to_id, from_id))
        c.execute("DELETE FROM cases WHERE id=?", (from_id,))
        c.execute("DELETE FROM reports WHERE case_id=?", (from_id,))


def list_audit(action: str | None = None) -> list[dict]:
    q = "SELECT * FROM audit_logs"
    args = []
    if action:
        q += " WHERE action=?"
        args.append(action)
    q += " ORDER BY id DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def counts() -> dict:
    with _conn() as c:
        def n(q):
            return c.execute(q).fetchone()[0]
        return {
            "alerts": n("SELECT COUNT(*) FROM alerts"),          # 收到（含抑制）
            "surfaced": n("SELECT COUNT(*) FROM alerts WHERE suppressed=0"),  # 上板
            "suppressed": n("SELECT COUNT(*) FROM alerts WHERE suppressed=1"),  # 被抑制
            "artifacts": n("SELECT COUNT(*) FROM artifacts"),
            "cases": n("SELECT COUNT(*) FROM cases"),
            "reports": n("SELECT COUNT(*) FROM reports"),
            "attack_chains": n("SELECT COUNT(*) FROM reports WHERE attack_chain_json != '[]'"),  # 系统2 真拼出攻击链的顶出案件数
            "audit": n("SELECT COUNT(*) FROM audit_logs"),
        }


def set_alert_verdict(alert_id: int, verdict: str) -> None:
    with _conn() as c:
        c.execute("UPDATE alerts SET verdict=? WHERE id=?", (verdict, alert_id))


def _all_alert_filter(source=None, suppressed=None, q=None):
    """原始告警流水筛选：来源 + 是否被抑制 + 关键词（raw/asset/type 模糊匹配）。"""
    wq = " WHERE 1=1"
    args = []
    if source:
        wq += " AND a.source=?"
        args.append(source)
    if suppressed == "1":
        wq += " AND a.suppressed=1"
    elif suppressed == "0":
        wq += " AND a.suppressed=0"
    if q:
        wq += " AND (a.raw LIKE ? OR a.asset LIKE ? OR a.type LIKE ?)"
        like = f"%{q}%"
        args += [like, like, like]
    return wq, args


def list_all_alerts(source=None, suppressed=None, q=None, sort="time", limit=50, offset=0):
    """原始告警流水：全部入库告警（含被抑制），带案件 uid，供「原始告警」页浏览。"""
    wq, args = _all_alert_filter(source, suppressed, q)
    order = _order_by(sort)
    sql = (f"SELECT a.*, c.correlation_uid AS case_uid FROM alerts a "
           f"LEFT JOIN cases c ON c.id = a.case_id{wq} ORDER BY {order} LIMIT ? OFFSET ?")
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args + [limit, offset]).fetchall()]


def count_all_alerts(source=None, suppressed=None, q=None) -> int:
    wq, args = _all_alert_filter(source, suppressed, q)
    with _conn() as c:
        return c.execute(f"SELECT COUNT(*) AS c FROM alerts a{wq}", args).fetchone()["c"]


def list_alerts_report(start=None, end=None, source=None, limit=100000):
    """报告用：按 created_at 时间范围（含边界）+ 来源查告警，带案件 uid。

    start/end 为 "YYYY-MM-DD HH:MM:SS" 字符串，可为空（= 不限）。
    """
    wq = " WHERE 1=1"
    args = []
    if start:
        wq += " AND a.created_at >= ?"
        args.append(start)
    if end:
        wq += " AND a.created_at <= ?"
        args.append(end)
    if source:
        wq += " AND a.source=?"
        args.append(source)
    sql = (f"SELECT a.*, c.correlation_uid AS case_uid FROM alerts a "
           f"LEFT JOIN cases c ON c.id = a.case_id{wq} ORDER BY a.id DESC LIMIT ?")
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, args + [limit]).fetchall()]


def set_case_reported_alerts(case_id: int, count: int) -> None:
    with _conn() as c:
        c.execute("UPDATE cases SET reported_at_alerts=? WHERE id=?", (count, case_id))


def alert_trend(range_hours: int, bucket_seconds: int) -> list[dict]:
    """告警流量时间序列：按时间桶统计 total（全部，含抑制）与 surfaced（上板）。

    created_at 为 SQLite datetime('now')（UTC，YYYY-MM-DD HH:MM:SS），用 strftime('%s') 转
    成 epoch 秒按桶聚合；缺口用零填充，返回完整连续序列。t 为桶起点 epoch 秒。
    """
    now = int(time.time())
    with _conn() as c:
        rows = c.execute(
            "SELECT strftime('%s', created_at) AS t, suppressed FROM alerts "
            "WHERE created_at != '' AND created_at >= datetime('now', ?)",
            (f"-{range_hours} hours",),
        ).fetchall()

    agg: dict[int, dict] = {}
    for r in rows:
        bucket = int(r["t"]) // bucket_seconds * bucket_seconds
        d = agg.setdefault(bucket, {"total": 0, "surfaced": 0})
        d["total"] += 1
        if not r["suppressed"]:
            d["surfaced"] += 1

    out: list[dict] = []
    nb = range_hours * 3600 // bucket_seconds  # 精确桶数（24h/时 → 24，7d/6h → 28，30d/日 → 30）
    end_bucket = now // bucket_seconds * bucket_seconds
    bucket = end_bucket - (nb - 1) * bucket_seconds
    for _ in range(nb):
        d = agg.get(bucket, {"total": 0, "surfaced": 0})
        out.append({"t": bucket, "total": d["total"], "surfaced": d["surfaced"]})
        bucket += bucket_seconds
    return out


# 案件状态机（对齐 agentic-soc 的合法转换）
CASE_TRANSITIONS = {
    "New": {"In Progress", "Closed"},
    "In Progress": {"On Hold", "Resolved", "Closed"},
    "On Hold": {"In Progress", "Resolved", "Closed"},
    "Resolved": {"In Progress", "Closed"},
    "Closed": {"In Progress"},
}


def is_valid_transition(current: str, new: str) -> bool:
    return current == new or new in CASE_TRANSITIONS.get(current, set())


# ---- 保留策略：归档/删除旧告警、案件、孤儿实体 ----

def alerts_older_than(cutoff: str) -> list[dict]:
    """取出 created_at 早于 cutoff 的告警（供归档）。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM alerts WHERE created_at < ? ORDER BY created_at", (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_alerts_older_than(cutoff: str) -> int:
    """删除 created_at 早于 cutoff 的告警，及其实体关联。"""
    with _conn() as c:
        c.execute(
            "DELETE FROM alert_artifacts WHERE alert_id IN "
            "(SELECT id FROM alerts WHERE created_at < ?)", (cutoff,),
        )
        cur = c.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff,))
        return cur.rowcount


def delete_orphan_artifacts() -> int:
    """删除不再被任何告警引用的孤儿实体。"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM artifacts WHERE id NOT IN "
            "(SELECT DISTINCT artifact_id FROM alert_artifacts)",
        )
        return cur.rowcount


def delete_cases_older_than(cutoff: str) -> int:
    """删除 created_at 早于 cutoff 的案件，及其报告。"""
    with _conn() as c:
        c.execute(
            "DELETE FROM reports WHERE case_id IN "
            "(SELECT id FROM cases WHERE created_at < ?)", (cutoff,),
        )
        cur = c.execute("DELETE FROM cases WHERE created_at < ?", (cutoff,))
        return cur.rowcount
