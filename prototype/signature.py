"""告警签名——把一条告警的「形状」抽成稳定签名，供免疫层细粒度匹配。

取代 (asset, type) 粗匹配：把会变的 token（IP / 哈希 / 独立数字）掩码掉，
保留语义 token（主机名 / 账号 / 描述词），匹配 = 签名精确相等。

借鉴日志模板抽取（Drain / Spell / LenMa）的核心思想：变量掩码 + 常量模板。
只做精确匹配，不上相似度 / embedding（零依赖、可解释、贴合现状）。
"""
from __future__ import annotations

import re

from artifact import _IP, _HASH

# 独立数字（端口 / 计数 / 字节）。负向 lookbehind 排除 [\w-]：
# 这样 web-01 / redis-cache-02 里连字符后的编号不被掩码；port=80 / bytes=4.2 会被掩码。
_NUM = re.compile(r"(?<![\w-])\d+(?:\.\d+)?")


def signature(source: str, type_: str, raw: str) -> str:
    """source|type|掩码后的 raw —— 一条告警的稳定「形状」。"""
    s = _IP.sub("<IP>", raw or "")
    s = _HASH.sub("<HASH>", s)
    s = _NUM.sub("<NUM>", s)
    return f"{source}|{type_}|{s}"
