"""Kafka 消费者线程组——消费日志云平台打到 Kafka 的日志，解析后增量入库。

与 syslog_server 走同一条管道（pipeline.process_signal）。无 Kafka 环境变量时静默跳过，
行为退化为现有 syslog 直收。
"""
from __future__ import annotations

import os
import threading
import time

import syslog as syslog_parser  # prototype/syslog.py，用于注入数据目录的解析配置路径

from app.core import logging as logging_setup
from app.services import pipeline, state
from app.services.kafka_adapter import parse

logger = logging_setup.get_logger("kafka")

_enabled = False
_consumer_thread: threading.Thread | None = None
_last_consume = None  # 最近一次成功消费的时间戳
_consumed = 0  # 累计消费条数


def config() -> dict:
    """读 Kafka 连接配置（环境变量，连外部已有 Kafka 只需改这里）。"""
    return {
        "servers": os.environ.get("NEUROIMMUNE_KAFKA_BOOTSTRAP_SERVERS", "").strip(),
        "topic": os.environ.get("NEUROIMMUNE_KAFKA_TOPIC", "").strip(),
        "group": os.environ.get("NEUROIMMUNE_KAFKA_GROUP", "neuroimmune").strip(),
        "auto_offset_reset": os.environ.get("NEUROIMMUNE_KAFKA_AUTO_OFFSET_RESET", "earliest").strip(),
    }


def status() -> dict:
    """供 /api/health 读取：消费者存活 + 累计消费 + 最近消费时间。"""
    return {
        "enabled": _enabled,
        "alive": _consumer_thread is not None and _consumer_thread.is_alive(),
        "consumed": _consumed,
        "last_consume": _last_consume,
    }


def start() -> None:
    global _enabled, _consumer_thread
    cfg = config()
    if not cfg["servers"] or not cfg["topic"]:
        logger.info("未配置 Kafka（NEUROIMMUNE_KAFKA_BOOTSTRAP_SERVERS / NEUROIMMUNE_KAFKA_TOPIC），跳过 Kafka 消费")
        return

    # 复用 syslog 解析器的来源/解析配置（数据目录播种 + 路径注入），与 syslog 直收一致。
    state.get_sources_config()
    state.get_parsers_config()
    syslog_parser._SOURCES_PATH = str(state.SOURCES_PATH)
    syslog_parser._PARSERS_PATH = str(state.PARSERS_PATH)

    def run() -> None:
        global _last_consume, _consumed
        while True:
            try:
                from kafka import KafkaConsumer
                consumer = KafkaConsumer(
                    cfg["topic"],
                    bootstrap_servers=cfg["servers"],
                    group_id=cfg["group"],
                    auto_offset_reset=cfg["auto_offset_reset"],
                    value_deserializer=lambda m: m.decode("utf-8", "replace"),
                )
                logger.info("Kafka 消费者已连接 %s，topic=%s", cfg["servers"], cfg["topic"])
                for msg in consumer:
                    sig = parse(msg.value)
                    if sig is None:
                        continue
                    try:
                        pipeline.process_signal(sig)
                        _consumed += 1
                        _last_consume = time.time()
                    except Exception:
                        logger.exception("Kafka 信号处理失败")
            except Exception:
                logger.exception("Kafka 消费异常，5 秒后重连")
                time.sleep(5)

    _consumer_thread = threading.Thread(target=run, daemon=True)
    _consumer_thread.start()
    _enabled = True
    logger.info("Kafka 消费线程已启动：%s topic=%s", cfg["servers"], cfg["topic"])
