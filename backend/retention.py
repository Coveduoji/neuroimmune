"""告警保留策略：归档旧告警（压缩 JSONL）→ 删除 → 清理孤儿实体；案件/报告留更久。

- 告警：超过 retention_alert_days 天 → 归档到 <数据目录>/archive/alerts-<日期>.jsonl.gz，再删库
- 案件/报告：超过 retention_case_days 天 → 删除（报告随案件）
- 实体：删除告警后清理无引用的孤儿 artifact
- 由 app.py 的夜间循环调用（与巩固同节奏），参数在「接入」配置里可调
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
import state
from paths import ARCHIVE_PATH


def _cutoff(days: int) -> str:
    """返回 UTC 的 'YYYY-MM-DD HH:MM:SS'，与 SQLite datetime('now') 存储格式一致。"""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _archive(alerts: list[dict]) -> int:
    """按日期把告警写入压缩 JSONL（追加模式：崩溃重跑最多重复归档，绝不丢数据）。"""
    if not alerts:
        return 0
    ARCHIVE_PATH.mkdir(parents=True, exist_ok=True)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for a in alerts:
        day = (a.get("created_at") or "unknown")[:10]
        by_day[day].append(a)
    for day, rows in by_day.items():
        p = ARCHIVE_PATH / f"alerts-{day}.jsonl.gz"
        with gzip.open(p, "at", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(alerts)


def run_retention() -> dict:
    cfg = state.get_ingest_config()
    alert_days = int(cfg.get("retention_alert_days", 30))
    case_days = int(cfg.get("retention_case_days", 180))

    # 告警：归档 → 删除 → 清理孤儿实体（cutoff 只算一次，避免归档与删除口径漂移）
    alert_cutoff = _cutoff(alert_days)
    old = db.alerts_older_than(alert_cutoff)
    archived = _archive(old)
    deleted = db.delete_alerts_older_than(alert_cutoff) if old else 0
    orphans = db.delete_orphan_artifacts() if old else 0

    # 案件/报告留更久
    removed_cases = db.delete_cases_older_than(_cutoff(case_days))

    return {
        "archived_alerts": archived,
        "deleted_alerts": deleted,
        "orphan_artifacts": orphans,
        "removed_cases": removed_cases,
    }
