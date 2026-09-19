"""Kafka 消息解析适配器——把 Kafka 消息转换成统一信号 schema。

产出与现有 syslog 解析一致的 `{time, source, asset, type, raw}`，供
`pipeline.process_signal` 直接消费。

当前默认假设消息是**原始 syslog 文本**（RFC3164/5424），复用 `prototype/syslog.py`
的 `parse_line`。若日志云平台投递 **JSON 结构化**消息，在 `parse` 里加一个 JSON 分支
即可（消费骨架与管道零改动）。
"""
from __future__ import annotations

import syslog as syslog_parser  # prototype/syslog.py（经 app/__init__.py 的 sys.path shim）


def parse(msg: bytes | str, src_ip: str = "") -> dict | None:
    """解析一条 Kafka 消息 → 统一信号 dict；解析不出返回 None。"""
    if isinstance(msg, bytes):
        text = msg.decode("utf-8", "replace")
    else:
        text = msg
    text = text.strip()
    if not text:
        return None

    # 默认：原始 syslog 文本，复用现有解析器（来源识别 + RFC 解析 + 配置解析）。
    # TODO(待确认消息格式)：若日志云平台投 JSON，在此按字段映射到信号 schema，例如：
    #   import json
    #   data = json.loads(text)
    #   return {"time": data.get("timestamp", "-"), "source": data.get("source", ""),
    #           "asset": data.get("asset", ""), "type": data.get("type", ""),
    #           "raw": text, "entities": data.get("entities")}
    return syslog_parser.parse_line(text, src_ip)
