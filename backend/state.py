"""全局状态（跨模块共享 + 持久化）：当前风险旋钮 + 四档阈值覆盖。

之前旋钮是 api/dashboard.py 里的内存变量，有两个问题：
1. syslog 流式路径读不到它，永远用默认档；
2. 服务重启就丢回「正常」。

这里改成持久化到 JSON 的单一事实源：当前档位 + 四档的阈值覆盖（配置 UI 可改，
不用碰 Python 代码）。HTTP 入库、syslog 流式、看板都读这里。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import config
import llm

KNOB_PATH = Path(__file__).resolve().parent / "knob.json"
PRESETS_PATH = Path(__file__).resolve().parent / "knob_presets.json"
_DEFAULT = "正常"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_knob_name() -> str:
    return _read(KNOB_PATH, {}).get("knob", _DEFAULT)


def set_knob_name(name: str) -> None:
    KNOB_PATH.write_text(json.dumps({"knob": name}, ensure_ascii=False), encoding="utf-8")


def _overrides() -> dict:
    return _read(PRESETS_PATH, {})


def get_knob(name: str) -> config.Knob:
    """取某档的实际参数：用户覆盖 > 默认。"""
    base = config.get_knob(name)
    ov = _overrides().get(name, {})
    return config.Knob(
        name=base.name,
        suppress_below=ov.get("suppress_below", base.suppress_below),
        escalate_above=ov.get("escalate_above", base.escalate_above),
        budget=ov.get("budget", base.budget),
    )


def set_preset(name: str, suppress_below: float, escalate_above: float, budget: int) -> None:
    ov = _overrides()
    ov[name] = {"suppress_below": suppress_below, "escalate_above": escalate_above, "budget": budget}
    PRESETS_PATH.write_text(json.dumps(ov, ensure_ascii=False), encoding="utf-8")


def get_all_presets() -> dict:
    return {name: {"suppress_below": get_knob(name).suppress_below,
                   "escalate_above": get_knob(name).escalate_above,
                   "budget": get_knob(name).budget}
            for name in config.PRESETS}


FREQ_PATH = Path(__file__).resolve().parent / "freq.json"


def get_freq_config() -> dict:
    """频率降级参数：时间窗(秒)/频次阈值/置信度折扣。"""
    return _read(FREQ_PATH, {"window": 3600, "threshold": 10, "demote": 0.4})


def set_freq_config(window: int, threshold: int, demote: float) -> None:
    FREQ_PATH.write_text(
        json.dumps({"window": window, "threshold": threshold, "demote": demote}, ensure_ascii=False),
        encoding="utf-8",
    )


# ---- 模型模式（mock / real / auto）+ 系统2 唤醒门槛 ----
MODE_PATH = Path(__file__).resolve().parent / "mode.json"
GATING_PATH = Path(__file__).resolve().parent / "gating.json"
_MODES = ("auto", "mock", "real")


def get_model_mode() -> str:
    m = _read(MODE_PATH, {}).get("mode", "auto")
    return m if m in _MODES else "auto"


def set_model_mode(mode: str) -> None:
    if mode not in _MODES:
        raise ValueError(f"未知模式 {mode}")
    MODE_PATH.write_text(json.dumps({"mode": mode}, ensure_ascii=False), encoding="utf-8")


# ---- 模型接入 / 检测调参 / 接入 配置（env 作为 fallback，UI 可改）----
MODEL_PATH = Path(__file__).resolve().parent / "model.json"
DETECTION_PATH = Path(__file__).resolve().parent / "detection.json"
INGEST_PATH = Path(__file__).resolve().parent / "ingest.json"


def get_model_config() -> dict:
    """模型接入：系统1/2 的 key/base_url/model + temperature/timeout。空值=回退 .env。"""
    return _read(MODEL_PATH, {
        "api_key": "", "base_url": "", "model": "",
        "deep_api_key": "", "deep_base_url": "", "deep_model": "",
        "temperature": 0.0, "timeout": 120,
    })


def set_model_config(cfg: dict) -> dict:
    merged = get_model_config()
    merged.update({k: v for k, v in cfg.items() if k in merged and v is not None})
    MODEL_PATH.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return merged


def get_detection_config() -> dict:
    """检测调参：案件强度/重分析/RAG/固有免疫/放回 + mock 规则。"""
    cfg = _read(DETECTION_PATH, {})
    return {
        "chain_bonus": cfg.get("chain_bonus", 0.10),
        "chain_cap": cfg.get("chain_cap", 0.30),
        "grew": cfg.get("grew", 2),
        "rag_limit": cfg.get("rag_limit", 5),
        "innate_conf": cfg.get("innate_conf", 0.95),
        "restore_conf": cfg.get("restore_conf", 0.9),
        "mock_indicators": cfg.get("mock_indicators", [list(x) for x in llm.DEFAULT_INDICATORS]),
        "mock_no_hit": cfg.get("mock_no_hit", 0.15),
        "mock_base": cfg.get("mock_base", 0.32),
        "mock_ceiling": cfg.get("mock_ceiling", 0.72),
        "mock_cutoff": cfg.get("mock_cutoff", 0.5),
    }


def set_detection_config(cfg: dict) -> dict:
    merged = get_detection_config()
    for k in merged:
        if k in cfg and cfg[k] is not None:
            merged[k] = cfg[k]
    DETECTION_PATH.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return merged


def get_ingest_config() -> dict:
    """接入：syslog bind/port、夜间巩固间隔（秒）、API token（空=免鉴权）。"""
    return _read(INGEST_PATH, {
        "syslog_bind": "0.0.0.0", "syslog_port": 5514,
        "consolidate_interval": 21600, "api_token": "",
    })


def set_ingest_config(cfg: dict) -> dict:
    merged = get_ingest_config()
    merged.update({k: v for k, v in cfg.items() if k in merged and v is not None})
    INGEST_PATH.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    return merged


def _mock_client() -> llm.MockClient:
    d = get_detection_config()
    return llm.MockClient(
        indicators=[tuple(x) for x in d["mock_indicators"]],
        no_hit=d["mock_no_hit"], base=d["mock_base"],
        ceiling=d["mock_ceiling"], cutoff=d["mock_cutoff"],
    )


def get_client():
    """按运行时模式 + 模型配置选系统1（杏仁核）客户端，syslog 流式与 HTTP 入库读同一份。

    auto=按有无 key 决定；mock=强制零成本 mock；real=强制真实（无 key 退回 mock）。
    """
    llm.load_dotenv()  # 把 .env 填进 os.environ（只补缺），作为 model.json 空值时的 fallback
    mode = get_model_mode()
    if mode == "mock":
        return _mock_client()
    m = get_model_config()
    api_key = m.get("api_key") or os.environ.get("NEUROIMMUNE_API_KEY", "").strip()
    if not api_key:
        return _mock_client()  # auto 或 real 都没 key → 退回 mock
    return llm.OpenAICompatClient(
        base_url=m.get("base_url") or os.environ.get("NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1"),
        api_key=api_key,
        model=m.get("model") or os.environ.get("NEUROIMMUNE_MODEL", "deepseek-chat"),
        temperature=m.get("temperature", 0.0),
        timeout=m.get("timeout", 120),
    )


def get_deep_client():
    """按运行时模式 + 模型配置选系统2（深想）客户端。"""
    llm.load_dotenv()
    mode = get_model_mode()
    if mode == "mock":
        return _mock_client()
    m = get_model_config()
    api_key = (m.get("deep_api_key") or m.get("api_key")
               or os.environ.get("NEUROIMMUNE_DEEP_API_KEY", "").strip()
               or os.environ.get("NEUROIMMUNE_API_KEY", "").strip())
    if not api_key:
        return _mock_client()
    return llm.OpenAICompatClient(
        base_url=(m.get("deep_base_url") or m.get("base_url")
                  or os.environ.get("NEUROIMMUNE_DEEP_BASE_URL", "").strip()
                  or os.environ.get("NEUROIMMUNE_BASE_URL", "https://api.deepseek.com/v1")),
        api_key=api_key,
        model=m.get("deep_model") or os.environ.get("NEUROIMMUNE_DEEP_MODEL", "deepseek-reasoner"),
        temperature=None,  # 推理模型不支持 temperature
        timeout=m.get("timeout", 120),
    )


def get_gating_config() -> dict:
    """系统2 唤醒门槛：单信号地板值 + 预算窗口秒数。"""
    return _read(GATING_PATH, {"single_signal_floor": 0.98, "budget_window": 3600})


def set_gating_config(single_signal_floor: float, budget_window: int) -> None:
    GATING_PATH.write_text(
        json.dumps({"single_signal_floor": single_signal_floor, "budget_window": budget_window},
                   ensure_ascii=False),
        encoding="utf-8",
    )


# ---- syslog 来源映射（prototype/syslog_sources.json，syslog.py 也读它）----
SOURCES_PATH = Path(__file__).resolve().parent.parent / "prototype" / "syslog_sources.json"


def get_sources_config() -> dict:
    return _read(SOURCES_PATH, {"facility": {}, "hostname": {}, "tag": {}, "ip": {}})


def set_sources_config(cfg: dict) -> dict:
    SOURCES_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg
