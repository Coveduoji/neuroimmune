"""内部资产匹配（纯函数，零依赖，不读库）。

资产清单由 backend 侧加载（读 assets 表 + 缓存），把 `[{role, value, criticality}]`
传进来，这里只负责「一个 IP/域名 属于哪个角色」的判定。

- IP：CIDR 网段 + 精确 IP，多角色命中取最长前缀（最具体）。
- 域名：后缀匹配（value == d 或 value 以 `.` + d 结尾）。
"""
from __future__ import annotations

import ipaddress


def match_asset(value: str, assets: list[dict]) -> dict | None:
    """判定 value 是否命中资产清单，返回 {role, criticality} 或 None。"""
    value = (value or "").strip()
    if not value or not assets:
        return None

    ip_networks: list[tuple[int, dict, ipaddress.IPv4Network | ipaddress.IPv6Network]] = []
    domains: list[tuple[dict, str]] = []

    for a in assets:
        v = (a.get("value") or "").strip()
        if not v:
            continue
        try:
            net = ipaddress.ip_network(v, strict=False)
            ip_networks.append((net.prefixlen, a, net))
        except ValueError:
            domains.append((a, v))

    # IP 匹配（最长前缀优先）
    try:
        ip = ipaddress.ip_address(value)
        best: tuple[int, dict] | None = None
        for prefix, a, net in ip_networks:
            if ip.version == net.version and ip in net:
                if best is None or prefix > best[0]:
                    best = (prefix, a)
        if best:
            a = best[1]
            return {"role": a.get("role", ""), "criticality": a.get("criticality", "normal")}
        return None
    except ValueError:
        pass  # 不是合法 IP，走域名后缀匹配

    # 域名后缀匹配
    for a, d in domains:
        if value == d or value.endswith("." + d):
            return {"role": a.get("role", ""), "criticality": a.get("criticality", "normal")}
    return None
