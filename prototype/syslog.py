"""syslog 解析器（本模块与标准库 syslog 同名，本目录优先导入本模块）。

把 RFC3164 / RFC5424 两种 syslog 行解析成统一信号 dict
{time, source, asset, type, raw}，供杏仁核管道直接消费。解析不出的返回 None。

来源（source）判定顺序（固定配置文件 prototype/syslog_sources.json，可自行增改）：
  1. tag      —— 应用名 / TAG 子串匹配（最精确，如 ossec→HIDS）
  2. hostname —— 主机名字串匹配（如 tiyan→天眼）
  3. facility —— RFC 编码（auth→认证…），内置默认 + 配置文件覆盖（local0→天眼 之类）
匹配均为大小写不敏感的子串包含；优先级 tag > hostname > facility。
"""
from __future__ import annotations

import json
import os
import re

import parsers

# 标准 facility 编码（RFC 3164 / 5424）
FACILITY = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon", 4: "auth", 5: "syslog",
    6: "lpr", 7: "news", 8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
    12: "ntp", 13: "audit", 14: "console", 15: "clock",
    16: "local0", 17: "local1", 18: "local2", 19: "local3",
    20: "local4", 21: "local5", 22: "local6", 23: "local7",
}

SEVERITY = {0: "emerg", 1: "alert", 2: "crit", 3: "err", 4: "warning", 5: "notice", 6: "info", 7: "debug"}

# facility → 信号 source（中文归类，内置默认；配置文件可覆盖/新增）
_SOURCE = {
    "kern": "内核", "user": "系统", "mail": "邮件", "daemon": "系统服务",
    "auth": "认证", "syslog": "系统", "lpr": "打印", "news": "新闻",
    "uucp": "其他", "cron": "计划任务", "authpriv": "权限", "ftp": "文件传输",
    "ntp": "时间同步", "audit": "审计", "console": "控制台", "clock": "计划任务",
}

_SOURCES_PATH = os.path.join(os.path.dirname(__file__), "syslog_sources.json")

# 解析配置路径：backend 启动时注入数据目录下的 syslog_parsers.json；
# prototype 独立跑时保持 None → 配置解析不启用，走 RFC + 兜底。
_PARSERS_PATH = None


def _load_sources() -> dict:
    try:
        with open(_SOURCES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_parsers() -> dict:
    if not _PARSERS_PATH:
        return {}
    try:
        with open(_PARSERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _source(fac: str, host: str = "", tag: str = "", src_ip: str = "") -> str:
    cfg = _load_sources()
    # 1) 来源 IP 最精确（网络发送方地址；子串匹配，可用完整 IP 或网段前缀如 "10.20."）
    for pat, label in cfg.get("ip", {}).items():
        if pat and str(pat) in src_ip:
            return label
    # 2) tag 次之
    for pat, label in cfg.get("tag", {}).items():
        if pat and str(pat).lower() in tag.lower():
            return label
    # 3) hostname
    for pat, label in cfg.get("hostname", {}).items():
        if pat and str(pat).lower() in host.lower():
            return label
    # 4) facility：内置默认 + 配置覆盖
    merged = dict(_SOURCE)
    merged.update(cfg.get("facility", {}))
    if fac in merged:
        return merged[fac]
    if fac.startswith("local"):
        return "应用"
    return "其他"


def _extract_pri(line: str) -> tuple[int | None, str]:
    if line.startswith("<"):
        m = re.match(r"^<(\d{1,3})>(.*)$", line, re.DOTALL)
        if m:
            return int(m.group(1)), m.group(2)
    return None, line


def _build(time: str, host: str, fac: str, tag: str, msg: str, src_ip: str = "") -> dict:
    return {
        "time": time or "-",
        "source": _source(fac, host, tag, src_ip),
        "asset": host or "",
        "type": fac,
        "raw": msg,
    }


def _parse_5424(rest: str, fac: str, src_ip: str = "") -> dict | None:
    # TIMESTAMP HOST APP PROCID MSGID [SD] MSG
    parts = rest.split(" ", 5)
    if len(parts) < 2:
        return None
    ts, host = parts[0], parts[1]
    tag = parts[2] if len(parts) > 2 else ""
    if tag == "-":
        tag = ""
    tail = parts[5] if len(parts) > 5 else ""
    m = re.match(r"^\[[^\]]*\]\s?(.*)$", tail, re.DOTALL)
    if m:
        msg = m.group(1).strip()
    else:
        msg = tail.strip()
        if msg.startswith("- "):
            msg = msg[2:].strip()
        elif msg == "-":
            msg = ""
    return _build(ts, host, fac, tag, msg, src_ip)


def _parse_3164(rest: str, fac: str, src_ip: str = "") -> dict | None:
    # TIMESTAMP HOST TAG[pid]: MSG
    m = re.match(r"^([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(.*)$", rest)
    ts, tail = (m.group(1), m.group(2)) if m else ("", rest)
    host, _, body = tail.partition(" ")
    tag = ""
    tm = re.match(r"^([^\s:\[]+)(?:\[\d+\])?:\s?(.*)$", body, re.DOTALL)
    if tm:
        tag, msg = tm.group(1), tm.group(2)
    else:
        msg = body.strip()
    return _build(ts, host, fac, tag, msg, src_ip)


def parse_line(line: str, src_ip: str = "") -> dict | None:
    """解析一行 syslog → 信号 dict；解析不出返回 None。

    src_ip 是网络发送方 IP（传输层对端地址），只用于「来源 IP → 来源名」映射
    （如 1.2.3.4 → 天眼），与告警消息体里的源 IP 字段无关。
    """
    line = line.strip()
    if not line:
        return None

    # 方案 C：识别来源（有 syslog 头用 host/tag，无头用 ip 映射），命中配置就走配置解析。
    host = tag = ""
    hm = re.match(r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)\s+(\S+):", line)
    if hm:
        host, tag = hm.group(1), hm.group(2)
    src_name = _source("", host, tag, src_ip)
    cfg = _load_parsers().get(src_name)
    if cfg:
        body = parsers.strip_syslog_header(line) if cfg.get("strip_syslog") else line
        sig = parsers.parse_configured(body, line, src_name, cfg)
        if sig is not None:
            return sig

    pri, rest = _extract_pri(line)
    fac = FACILITY.get(pri // 8, "user") if pri is not None else "user"
    # RFC5424：PRI 后紧跟版本号（纯数字）
    if re.match(r"^\d+\s", rest):
        rest = rest.split(" ", 1)[1]
        return _parse_5424(rest, fac, src_ip)
    # RFC3164：有 PRI 或可识别的 "Mmm dd hh:mm:ss" 时间戳；都不是则兜底存 raw（不丢弃）。
    if pri is None and not re.match(r"^[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", rest):
        return _build("", "", "syslog", "", line, src_ip)
    return _parse_3164(rest, fac, src_ip)
