"""syslog 接收线程——UDP+TCP 监听，解析后增量入库（24h 值守）。

由 app.py 在启动时调用 start()，复用 prototype/syslog.py 的解析器，
每条解析出的信号走 pipeline.process_signal 增量落库。一个进程同时是 API + syslog 接收。
"""
from __future__ import annotations

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

import logging_setup
import pipeline
import state

logger = logging_setup.get_logger("syslog")


def _udp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(65535)
            src_ip = addr[0] if addr else ""
            for line in data.decode("utf-8", "replace").splitlines():
                if line.strip():
                    q.put((src_ip, line))
        except OSError:
            break


def _tcp_loop(bind: str, port: int, q: queue.Queue, stop: threading.Event) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.listen(50)
    while not stop.is_set():
        try:
            conn, addr = sock.accept()
        except OSError:
            break
        threading.Thread(target=_tcp_conn, args=(conn, addr, q, stop), daemon=True).start()


def _tcp_conn(conn: socket.socket, addr, q: queue.Queue, stop: threading.Event) -> None:
    src_ip = addr[0] if addr else ""
    with conn:
        f = conn.makefile("r", encoding="utf-8", errors="replace")
        for line in f:
            if stop.is_set():
                break
            if line.strip():
                q.put((src_ip, line.strip()))


# 健康监控用的状态
listening = False
last_ingest = None  # 最近一次成功入库的时间戳
_udp_thread: threading.Thread | None = None
_tcp_thread: threading.Thread | None = None
_worker_threads: list[threading.Thread] = []


def status() -> dict:
    """供 /api/health 读取：反映线程真实存活，而非启动时只设一次的布尔。"""
    workers_alive = bool(_worker_threads) and all(t.is_alive() for t in _worker_threads)
    alive = workers_alive and all(
        t is not None and t.is_alive() for t in (_udp_thread, _tcp_thread)
    )
    return {
        "listening": alive,
        "udp_alive": _udp_thread is not None and _udp_thread.is_alive(),
        "tcp_alive": _tcp_thread is not None and _tcp_thread.is_alive(),
        "worker_alive": workers_alive,
        "workers": len(_worker_threads),
        "last_ingest": last_ingest,
    }


def start(bind: str | None = None, port: int | None = None) -> None:
    global listening, _udp_thread, _tcp_thread, _worker_threads
    # 来源映射统一持久化到数据目录：缺失时播种，并让解析器读数据目录那份（而非源码目录默认文件）。
    state.get_sources_config()
    syslog_parser._SOURCES_PATH = str(state.SOURCES_PATH)
    # 接入配置（设置页可改）优先，环境变量 fallback。改 bind/port 需重启后端（socket 已绑定）。
    ingest = state.get_ingest_config()
    bind = bind or ingest.get("syslog_bind")
    port = port or int(ingest.get("syslog_port"))
    q: queue.Queue = queue.Queue()
    stop = threading.Event()

    _udp_thread = threading.Thread(target=_udp_loop, args=(bind, port, q, stop), daemon=True)
    _tcp_thread = threading.Thread(target=_tcp_loop, args=(bind, port, q, stop), daemon=True)
    _udp_thread.start()
    _tcp_thread.start()

    def worker() -> None:
        global last_ingest
        while not stop.is_set():
            try:
                src_ip, line = q.get(timeout=1)
            except queue.Empty:
                continue
            sig = syslog_parser.parse_line(line, src_ip)
            if sig is None:
                continue
            try:
                pipeline.process_signal(sig)
                last_ingest = time.time()
            except Exception:
                logger.exception("syslog 信号处理失败")

    # 多 worker 并发消费队列：worker 数对齐小模型（杏仁核）并发上限。模型调用在
    # process_signal 内被信号量限流，worker 数再多也会阻塞在信号量上，取并发上限即可。
    n_workers = state.judge_concurrency()
    _worker_threads = [threading.Thread(target=worker, daemon=True) for _ in range(n_workers)]
    for t in _worker_threads:
        t.start()
    listening = True
    logger.info("已监听 UDP/TCP %s:%s，%d 个 worker 增量入库中", bind, port, n_workers)
