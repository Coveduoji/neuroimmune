"""syslog 接收线程——UDP+TCP 监听，解析后增量入库（24h 值守）。

由 app.py 在启动时调用 start()，复用 prototype/syslog.py 的解析器，
每条解析出的信号走 pipeline.process_signal 增量落库。一个进程同时是 API + syslog 接收。
"""
from __future__ import annotations

import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path

PROTO = str(Path(__file__).resolve().parent.parent / "prototype")
if PROTO not in sys.path:
    sys.path.insert(0, PROTO)

import syslog as syslog_parser

import pipeline
import state


def _udp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    while not stop.is_set():
        try:
            data, _ = sock.recvfrom(65535)
            for line in data.decode("utf-8", "replace").splitlines():
                if line.strip():
                    q.put(line)
        except OSError:
            break


def _tcp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.listen(50)
    while not stop.is_set():
        try:
            conn, _ = sock.accept()
        except OSError:
            break
        threading.Thread(target=_tcp_conn, args=(conn, q, stop), daemon=True).start()


def _tcp_conn(conn: socket.socket, q: queue.Queue, stop: threading.Event) -> None:
    with conn:
        f = conn.makefile("r", encoding="utf-8", errors="replace")
        for line in f:
            if stop.is_set():
                break
            if line.strip():
                q.put(line.strip())


# 健康监控用的状态
listening = False
last_ingest = None  # 最近一次成功入库的时间戳


def start(bind: str | None = None, port: int | None = None) -> None:
    global listening
    # 接入配置（设置页可改）优先，环境变量 fallback。改 bind/port 需重启后端（socket 已绑定）。
    ingest = state.get_ingest_config()
    bind = bind or ingest.get("syslog_bind") or os.environ.get("NEUROIMMUNE_SYSLOG_BIND", "0.0.0.0")
    port = port or int(ingest.get("syslog_port") or os.environ.get("NEUROIMMUNE_SYSLOG_PORT", "5514"))
    q: queue.Queue = queue.Queue()
    stop = threading.Event()

    threading.Thread(target=_udp_loop, args=(bind, port, q, stop), daemon=True).start()
    threading.Thread(target=_tcp_loop, args=(bind, port, q, stop), daemon=True).start()

    def worker() -> None:
        global last_ingest
        while not stop.is_set():
            try:
                line = q.get(timeout=1)
            except queue.Empty:
                continue
            sig = syslog_parser.parse_line(line)
            if sig is None:
                continue
            try:
                pipeline.process_signal(sig)
                last_ingest = time.time()
            except Exception as e:
                print(f"[syslog] 处理失败: {e}")

    threading.Thread(target=worker, daemon=True).start()
    listening = True
    print(f"[syslog] 已监听 UDP/TCP {bind}:{port}，增量入库中")
