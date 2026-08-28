"""告警签名——把一条告警的「形状」抽成稳定签名，供免疫层细粒度匹配。

取代 (asset, type) 粗匹配：把会变的 token（IP / 哈希 / 独立数字 / UUID）掩码掉，
保留语义 token（主机名 / 账号 / 描述词），匹配 = 签名精确相等。

借鉴日志模板抽取（Drain / Spell / LenMa）的核心思想：变量掩码 + 常量模板。
只做精确匹配，不上相似度 / embedding（零依赖、可解释、贴合现状）。

退化兜底：若掩码后的 raw 里没有任何语义标识符（主机名/账号等），说明 raw 只剩
通用描述（如「检测到端口扫描」），此时签名会退化成 source|type，导致不同资产共用
同一签名、黑白名单跨资产误伤。于是追加「明文 asset」进签名区分资产——asset 不掩码，
目的就是让「资产 A 的端口扫描」和「资产 B 的端口扫描」成为不同签名。
"""
from __future__ import annotations

import re

from artifact import _HASH, _IDENT, _IP

# 独立数字（端口 / 计数 / 字节）。负向 lookbehind 排除 [\w-]：
# 这样 web-01 / redis-cache-02 里连字符后的编号不被掩码；port=80 / bytes=4.2 会被掩码。
_NUM = re.compile(r"(?<![\w-])\d+(?:\.\d+)?")

# IPv6（启发式）：含 :: 压缩形式在前（避免被无压缩分支拆开），无压缩（≥3 段）在后，
# 不追求 RFC 完全；纯短压缩 ::1 掩不到，可接受。注意：会顺带把 HH:MM:SS 时间戳掩成 <IP>，
# 但时间戳本就被掩、不影响签名稳定性。
_IPV6 = re.compile(
    r"\b[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*::[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4})*\b"    # 含 ::
    r"|\b(?:[0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4})*\b"                    # 无压缩，≥3 段
)

# UUID（8-4-4-4-12）。
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def signature(source: str, type_: str, raw: str, asset: str = "") -> str:
    """source|type|[asset|]掩码后的 raw —— 一条告警的稳定「形状」。

    asset 仅当掩码后 raw 缺语义标识符时追加（见模块 docstring），否则保持原格式，
    避免对已含主机名/账号的告警过度细分。
    """
    s = _IP.sub("<IP>", raw or "")
    s = _HASH.sub("<HASH>", s)
    s = _IPV6.sub("<IP>", s)
    s = _UUID.sub("<UUID>", s)
    s = _NUM.sub("<NUM>", s)
    if asset and not _IDENT.search(s):
        return f"{source}|{type_}|{asset}|{s}"
    return f"{source}|{type_}|{s}"
