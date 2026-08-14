#!/usr/bin/env python3
"""真实模型全量回归：attack-day.jsonl → Web 后端增量管道（process_signal）。

与 /api/ingest 端点完全相同的代码路径（逐条 process_signal），只是省掉 HTTP 层。
用 .env 里的真实模型（DeepSeek），验证 1000 条告警的降噪 + 攻击链顶出 + 系统2报告。

用法：
    python3 run_real_test.py
    python3 run_real_test.py --input ../prototype/data/attack-day.jsonl --knob 正常
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

import db
import pipeline
import signals
import state


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(Path(__file__).resolve().parent.parent
                                          / "prototype" / "data" / "attack-day.jsonl"))
    ap.add_argument("--knob", default="正常")
    args = ap.parse_args()

    db.init_db()
    db.reset()
    state.set_knob_name(args.knob)

    sigs = signals.load_signals(args.input)
    print(f"真实模型全量入库：{len(sigs)} 条，旋钮={args.knob}", flush=True)

    t0 = time.time()
    agg = {"total": 0, "surfaced": 0, "suppressed": 0, "error": 0}
    for i, sig in enumerate(sigs, 1):
        try:
            r = pipeline.process_signal(sig, args.knob)
        except Exception as e:  # 单条失败不中断整轮（网络/限流容错）
            agg["error"] += 1
            print(f"[错误 #{i}] {type(e).__name__}: {e}", flush=True)
            continue
        agg["total"] += 1
        if r.get("status") == "suppressed":
            agg["suppressed"] += 1
        else:
            agg["surfaced"] += 1
        if i % 25 == 0 or i == len(sigs):
            el = time.time() - t0
            c = db.counts()
            print(f"进度 {i}/{len(sigs)}  用时 {el:.0f}s  上板 {agg['surfaced']}  "
                  f"抑制 {agg['suppressed']}  错误 {agg['error']}  案件 {c['cases']}  报告 {c['reports']}",
                  flush=True)

    # 等系统2后台线程（deepseek-reasoner 较慢）把报告写进库
    thr = state.get_knob(args.knob).escalate_above
    print(f"\n等待系统2写完报告（顶出线 {thr}）…", flush=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        pending = 0
        for case in db.list_cases(limit=200):
            if case["strength"] >= thr and not db.get_case_report(case["id"]):
                pending += 1
        if pending == 0:
            break
        print(f"  还有 {pending} 个顶出案件在等系统2 …", flush=True)
        time.sleep(5)
    else:
        print("  等待超时（部分系统2报告可能未完成）", flush=True)

    # ---- 汇总 ----
    print(f"\n===== 结果（旋钮={args.knob}）=====")
    print(f"总数 {agg['total']}  上板 {agg['surfaced']}  抑制 {agg['suppressed']}  错误 {agg['error']}")
    print(f"DB：{db.counts()}")

    print(f"\n----- 顶出案件（强度 >= {thr} 且有系统2报告）-----")
    for case in db.list_cases(limit=200):
        report = db.get_case_report(case["id"])
        if case["strength"] >= thr and report:
            alerts = db.get_case_alerts(case["id"])
            print(f"\n案件 {case['correlation_uid']}  强度 {case['strength']}  告警 {len(alerts)} 条  {case['title']}")
            print(f"  系统2定性：{report.get('verdict')} / {report.get('confidence')}")
            print(f"  摘要：{report.get('digest')}")
            for a in alerts:
                print(f"    [{a['time']}] {a['source']} · {a['asset']} · {a['type']}  conf={a['confidence']:.2f}")

    print(f"\n----- 上板但未顶出的案件（误报候选，可标记 False Positive）-----")
    for case in db.list_cases(limit=200):
        if case["strength"] < thr:
            alerts = db.get_case_alerts(case["id"])
            print(f"  案件 {case['correlation_uid']}  强度 {case['strength']}  告警 {len(alerts)} 条  {case['title']}")


if __name__ == "__main__":
    main()
