"""FastAPI 应用——把管道结果通过 REST 暴露给 React 客户端。"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

# 让后端能 import prototype 的核心模块（amygdala/graph/system2/tolerance/innate/config/llm）
PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import auth
import db
import state
import syslog_server
from api import auth as auth_api
from api import cases, dashboard, ingest as ingest_api

app = FastAPI(title="神经免疫防御", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(auth_api.router)
app.include_router(ingest_api.router)

db.init_db()
auth.bootstrap_admin()

# 24h 值守：启动时开 syslog 监听线程，实时增量入库
try:
    syslog_server.start()
except OSError as e:
    print(f"[syslog] 启动失败（端口可能被占用）: {e}")


# 夜间巩固：定时从 SQLite 蒸馏（间隔在设置页「接入」可改，热生效）
def _consolidate_loop() -> None:
    while True:
        interval = int(state.get_ingest_config().get("consolidate_interval", 21600))
        time.sleep(interval)
        try:
            import nightly
            r = nightly.consolidate()
            print(f"[consolidate] {r.get('status')}，新固有免疫规则 {len(r.get('new_rules', []))} 条")
        except Exception as e:
            print(f"[consolidate] 失败: {e}")


threading.Thread(target=_consolidate_loop, daemon=True).start()


@app.get("/")
def root():
    return {"service": "neuroimmune", "status": "ok", "counts": db.counts()}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "db": db.counts(),
        "syslog": {"listening": syslog_server.listening, "last_ingest": syslog_server.last_ingest},
        "knob": state.get_knob_name(),
        "mode": state.get_model_mode(),
    }
