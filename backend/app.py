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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

import auth
import db
import llm
import logging_setup
import state
import syslog_server
from api import auth as auth_api
from api import cases, dashboard, ingest as ingest_api

logger = logging_setup.get_logger("app")

app = FastAPI(title="神经免疫防御", version="0.1.0")

# 生产默认同源部署（nginx 反代 /api），无需跨域；前后端分域时用 NEUROIMMUNE_CORS_ORIGINS 逗号分隔。
_cors_origins = [o.strip() for o in os.environ.get("NEUROIMMUNE_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Host 头校验（默认放行，可用 NEUROIMMUNE_ALLOWED_HOSTS 逗号分隔收紧）。
_allowed_hosts = [h.strip() for h in os.environ.get("NEUROIMMUNE_ALLOWED_HOSTS", "*").split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(auth_api.router)
app.include_router(ingest_api.router)

logging_setup.setup_logging()

# 启动时先统一加载 .env（管理员账号 / JWT 密钥 / 模型 key 等），
# 否则 bootstrap_admin 在 import 期读不到 prototype/.env 里的管理员凭据。
llm.load_dotenv()

db.init_db()
auth.bootstrap_admin()

# 24h 值守：启动时开 syslog 监听线程，实时增量入库
try:
    syslog_server.start()
except OSError as e:
    logger.warning("syslog 启动失败（端口可能被占用）: %s", e)


# 夜间巩固：定时从 SQLite 蒸馏（间隔在设置页「接入」可改，热生效）
def _consolidate_loop() -> None:
    while True:
        interval = int(state.get_ingest_config().get("consolidate_interval", 21600))
        time.sleep(interval)
        try:
            import nightly
            r = nightly.consolidate()
            logger.info("夜间巩固 %s，新固有免疫规则 %s 条", r.get("status"), len(r.get("new_rules", [])))
        except Exception:
            logger.exception("夜间巩固失败")


threading.Thread(target=_consolidate_loop, daemon=True).start()


# 前端静态托管（无 nginx 的部署方式）：存在 frontend/dist 时，后端直接给 SPA（同源，免跨域/免反代）。
# 用 NEUROIMMUNE_STATIC_DIR 指定产物目录；不存在时退回 JSON 横幅（纯 API 模式 / nginx 反代模式）。
_STATIC_DIR = Path(os.environ.get(
    "NEUROIMMUNE_STATIC_DIR",
    str(Path(__file__).resolve().parent.parent / "frontend" / "dist"),
))

if _STATIC_DIR.is_dir():
    _assets = _STATIC_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/")
    def spa():
        return FileResponse(str(_STATIC_DIR / "index.html"))
else:

    @app.get("/")
    def root():
        return {"service": "neuroimmune", "status": "ok", "counts": db.counts()}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "db": db.counts(),
        "syslog": syslog_server.status(),
        "knob": state.get_knob_name(),
        "mode": state.get_model_mode(),
    }
