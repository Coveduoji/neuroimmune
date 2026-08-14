"""信号加载器——从真实数据文件读信号流（JSONL / JSON / CSV）。

取代原来写死的 synthetic_signals()：数据现在放在 data/sample.jsonl 里。
换真实 SIEM/EDR 导出，只要把文件路径传给 load_signals()，字段对上即可。

统一 schema（每条信号五个字段）：
    time    时间戳
    source  来源（身份/云/数据/流量/登录…）
    asset   关联主体（账号/主机/桶，统一叫 asset）
    type    类型（登录/身份/流量/导出/心跳…）
    raw     原始文本（杏仁核真正去读的那一段）

可选字段 label：ground-truth 标注，"benign"=已确认误报（免疫耐受回写用，只有 demo 需要）。
"""
from __future__ import annotations

import csv
import json
import os

REQUIRED = ("time", "source", "asset", "type", "raw")

# 内置样例：README 巅峰场景（凌晨 3:14 供应链投毒）的极简复刻。
# 大部分是噪声，埋了一条 4 弱信号拼成的攻击链，加一条临界信号演示风险旋钮。
SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "data", "sample.jsonl")


def _validate(sig: dict) -> dict:
    missing = [k for k in REQUIRED if k not in sig]
    if missing:
        raise ValueError(f"信号缺字段 {missing}: {sig!r}")
    return sig


def _load_jsonl(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(_validate(json.loads(line)))
    return out


def _load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON 顶层必须是数组")
    return [_validate(s) for s in data]


def _load_csv(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.append(_validate(row))
    return out


_LOADERS = {".jsonl": _load_jsonl, ".json": _load_json, ".csv": _load_csv}


def load_signals(path: str) -> list[dict]:
    """读信号文件；按扩展名选解析器。"""
    ext = os.path.splitext(path)[1].lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"不支持的文件类型 {ext!r}（支持 .jsonl / .json / .csv）")
    return loader(path)
