# 神经免疫防御 · NeuroImmune Defense

> 用「神经系统 + 免疫系统」架构编排多模型，构建一个**成本不对称、会学习、可调风险姿态**的企业 SOC 防守有机体。

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Node](https://img.shields.io/badge/node-18+-green) ![Status](https://img.shields.io/badge/status-开发中-orange)

神经免疫防御是一个多模型安全编排平台：把海量安全告警在边缘用廉价模型筛掉，只对少数可疑信号唤醒昂贵模型深想，并借「免疫记忆」持续把误报与已知攻击沉淀为规则，让防守体系越用越准。

## 核心价值

- **告警降噪** — 系统 1（廉价模型）常驻初筛，系统 2（昂贵模型）按需唤醒，把告警压到人能处理的量级。
- **越用越准** — 夜间离线巩固，把误报模式写进免疫耐受、把新 TTP 写进固有免疫，形成跨天记忆。
- **可调风险姿态** — 一个全局「风险旋钮」把「我要多安全」映射到检测阈值与响应激进程度，管理层可拨档。

## 特性

- **系统 1 / 系统 2 路由**：便宜模型初筛、贵模型深想，按需付费而非按量付费
- **黑板（全局工作空间）**：统一 schema，跨源信号按显著性打分拼链，两个弱信号可拼出一条攻击链
- **免疫层**：固有免疫（规则秒拦）、适应性免疫（行为基线）、免疫耐受（误报白名单）
- **记忆层**：睡眠巩固 + 免疫记忆，离线整合、检索记忆、回写规则
- **风险旋钮**：宽松 / 正常 / 保守 / 战时 四档，全局生效
- **Web 工作台**：看板 / 海马体关系图 / 分诊队列 / 丘脑告警流 / 免疫规则 / 设置
- **24h syslog 值守**：UDP+TCP 实时接入，增量入库
- **Mock 模式**：不配 key 也能零成本跑通全链路

## 架构

| 层 | 大脑对应 | 职责 |
|---|---|---|
| 感知层 | 杏仁核 + 抑制 | 常驻廉价模型，只判「有没有不该发生的」，产出带置信度的信号 |
| 注意力层 | 黑板 / 全局工作空间 | 统一 schema，显著性打分 + 跨源关联拼链 |
| 认知层 | 系统 1 / 系统 2 | 快判断 / 深分析，告警降噪 |
| 响应层 | 风险旋钮 | 全局阈值档位，管理层的方向盘 |
| 记忆层 | 睡眠巩固 + 免疫记忆 | 离线整合、检索记忆、回写规则 |
| 免疫层 | 固有 / 适应 / 耐受 | 规则秒拦 + 行为基线 + 误报白名单 |

### 设计原则

1. 贵的模型要「**睡眠**」，便宜的模型要「**专门**」
2. 一个全局旋钮管「**状态**」
3. 一半力气花在「**抑制**」而不是「生成」
4. 记忆靠「**离线巩固**」而不是「现场硬记」

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+

### 一键启动

```bash
./start.sh          # 后端 :8000 + 前端 :5173，首次运行自动装依赖
```

打开 <http://localhost:5173>。后端自带 syslog 接收（UDP/TCP `:5514`）。

### 手动启动

```bash
# 后端（FastAPI :8000）
cd backend && pip install -r requirements.txt
uvicorn app:app --port 8000

# 前端（Vite :5173，/api 代理到 :8000）
cd frontend && npm install && npm run dev
```

### 最小闭环原型（无 Web，mock 模型）

```bash
cd prototype && python3 main.py      # 读内置样例 data/sample.jsonl
```

## 配置

模型与 syslog 参数统一在 `prototype/.env`（详见 [`backend/README.md`](backend/README.md)）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `NEUROIMMUNE_API_KEY` | 空 | 杏仁核（系统 1）模型 key；**留空 = mock**（零成本跑通） |
| `NEUROIMMUNE_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点（DeepSeek / OpenRouter / Ollama / vLLM） |
| `NEUROIMMUNE_MODEL` | `deepseek-chat` | 系统 1（初筛）模型 |
| `NEUROIMMUNE_DEEP_MODEL` | `deepseek-reasoner` | 系统 2（深想）模型 |
| `NEUROIMMUNE_SYSLOG_BIND` / `_PORT` | `0.0.0.0` / `5514` | syslog 接收地址 / 端口 |
| `NEUROIMMUNE_API_TOKEN` | 空 | 设了则所有写操作需带 `X-API-Token` |

## 文档

- [`PRODUCT.md`](PRODUCT.md) — 产品定位与价值主张
- [`PROGRESS.md`](PROGRESS.md) — 当前进展与待办
- [`backend/README.md`](backend/README.md) — Web 工作台运行手册
- [`prototype/README.md`](prototype/README.md) — 最小闭环原型使用说明
- [`prototype/ROADMAP.md`](prototype/ROADMAP.md) — 路线图
- [`discussion-log.md`](discussion-log.md) — 设计脉络记录

## 项目结构

```
.
├── backend/       FastAPI 服务（REST API + 24h syslog 值守 + 定时巩固）
├── frontend/      React + Vite 单页应用
├── prototype/     核心判断逻辑（杏仁核 / 黑板 / 系统2 / 免疫，被 backend 复用）
├── start.sh       一键启动脚本
├── PRODUCT.md     产品文档
├── PROGRESS.md    进展记录
└── README.md
```

## License

尚未选定开源许可证。
