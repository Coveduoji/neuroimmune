"""CLI：读信号文件（JSONL/JSON/CSV）→ 跑管道 → 落库。

用法：
    python3 ingest.py ../prototype/data/sample.jsonl            # 默认重置库再入库
    python3 ingest.py ../prototype/data/sample.jsonl --knob 保守
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

import signals

import db
import pipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="信号文件路径（.jsonl/.json/.csv）")
    ap.add_argument("--knob", default="正常")
    args = ap.parse_args()

    sigs = signals.load_signals(args.input)
    db.init_db()
    db.reset()
    print(f"入库 {len(sigs)} 条信号，旋钮={args.knob} …")
    result = pipeline.process(sigs, args.knob)
    c = result["counts"]
    print(f"  总数 {c['total']}  上板 {c['surfaced']}  归案 {c['components']}  顶出 {c['escalated']}")
    print(f"  耐受 {c['tol_suppressed']}  秒拦 {c['innate_hits']}  抑制 {c['suppressed']}")
    for cs in result["cases"]:
        tag = "顶出" if cs["escalated"] else "未顶出"
        print(f"  案件 {cs['correlation_uid']}  强度 {cs['strength']}  {cs['alerts']} 条  [{tag}]")
    print(f"  DB 状态：{db.counts()}")


if __name__ == "__main__":
    main()
