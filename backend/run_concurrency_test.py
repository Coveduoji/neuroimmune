#!/usr/bin/env python3
"""并发压力测试（mock 模式，不真调模型）：验证并发归案正确性 + 稳定性 + 吞吐参考。

用 gen_attack_data 生成多源数据（内嵌 7 条跨设备攻击链），多线程并发灌入
pipeline.process_signal，模拟多设备 syslog 并发接入。全程 mock（强制 mode=mock），
零模型调用、零费用。

测什么：
1. 正确性 —— 乱序并发下，攻击链 7 条是否仍正确拼成 1 个案件（无重复建案/丢信号）。
2. 稳定性 —— 并发写 SQLite 无 database is locked、无死锁、无未捕获异常。
3. 吞吐参考 —— mock 下瓶颈在 DB/归案锁；真实吞吐提升需真模型（模型调用才是真瓶颈）。

用法：
    python3 run_concurrency_test.py                 # 2000 条，5 worker
    python3 run_concurrency_test.py --n 5000 --workers 20
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 必须在 import backend 模块前设置隔离数据目录（paths.DB_PATH 在 import 时求值）
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "prototype"))
sys.path.insert(0, str(_ROOT / "backend"))
_TMP = tempfile.mkdtemp(prefix="neuroimmune-test-")
os.environ["NEUROIMMUNE_DATA_DIR"] = _TMP

import gen_attack_data  # noqa: E402
import db  # noqa: E402
import pipeline  # noqa: E402
import state  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260815)
    args = ap.parse_args()

    # 强制 mock：mode 锁到 mock，确保零模型调用（即使环境里 export 了 API key）
    state.set_model_mode("mock")
    db.init_db()

    sigs = gen_attack_data.generate(args.n, args.seed)
    print(f"生成 {len(sigs)} 条多源信号（内嵌 7 条攻击链），mock 模式，"
          f"{args.workers} worker 并发灌入", flush=True)

    t0 = time.time()
    errors: list[str] = []

    def ingest(sig: dict) -> dict:
        return pipeline.process_signal(sig)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(ingest, s) for s in sigs]
        for i, f in enumerate(futs, 1):
            try:
                f.result()
            except Exception as e:  # 单条失败不中断，收集错误（重点盯 database is locked）
                errors.append(f"#{i} {type(e).__name__}: {e}")

    el = time.time() - t0
    c = db.counts()

    print(f"\n===== 并发测试结果 =====")
    print(f"信号 {len(sigs)}  并发 {args.workers}  耗时 {el:.2f}s  吞吐 {len(sigs)/el:.0f} 条/秒")
    print(f"DB：告警(含抑制) {c['alerts']}  上板 {c['surfaced']}  抑制 {c['suppressed']}  "
          f"案件 {c['cases']}  报告 {c['reports']}  实体 {c['artifacts']}")
    print(f"处理错误 {len(errors)}")

    # 攻击链归案校验：10.20.1.10 是攻击链关键共享 IP（连接 web-mall-01 ↔ svc_deploy），
    # 且 10.20.0.0/16 段只被攻击链使用，不与噪声（10.10./172.16.）重叠。
    chain_cases = db.cases_for_entity("ip", "10.20.1.10")
    print(f"\n攻击链关键 IP 10.20.1.10 命中的案件数：{len(chain_cases)}（期望 1）")
    if chain_cases:
        case = chain_cases[0]
        alerts = db.get_case_alerts(case["id"])
        print(f"该案件告警数：{len(alerts)}（期望 7，即完整攻击链）")
        for a in alerts:
            print(f"  [{a['time']}] {a['source']} · {a['asset']} · conf={a['confidence']:.2f}")

    print(f"\n全部 {c['cases']} 个案件（上板案件，含误报/攻击链）：")
    for case in db.list_cases(limit=200):
        na = len(db.get_case_alerts(case["id"]))
        print(f"  {case['correlation_uid']}  强度 {case['strength']:.2f}  {na} 条  {case['title']}")

    # 断言
    ok = True
    if errors:
        print(f"\n❌ 有 {len(errors)} 条处理失败，前 10 条：")
        for e in errors[:10]:
            print(f"   {e}")
        ok = False
    if len(chain_cases) != 1:
        print(f"\n❌ 攻击链归案错误：10.20.1.10 命中 {len(chain_cases)} 个案件（期望 1）")
        ok = False
    if chain_cases and len(db.get_case_alerts(chain_cases[0]["id"])) != 7:
        print(f"\n❌ 攻击链不完整：该案告警数 != 7")
        ok = False

    print(f"\n{'✅ PASS' if ok else '❌ FAIL'}："
          f"并发归案正确（攻击链 7 条拼 1 案）、无错误、无竞态")


if __name__ == "__main__":
    main()
