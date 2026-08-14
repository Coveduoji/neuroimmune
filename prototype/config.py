"""风险旋钮（响应层，精简版）——把「我要多安全」抽成几档预设，映射到三个旋钮。

README 3.2：风险旋钮实现成本≈0，但价值完全依赖杏仁核+黑板先跑起来。
三个旋钮 = 杏仁核抑制线 + 黑板顶出线 + 系统2 深度算力预算。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Knob:
    name: str
    # 杏仁核抑制阈值：置信度低于此 → 静默，不上黑板（抑制机制，压误报）
    suppress_below: float
    # 黑板顶出阈值：显著性 >= 此值 → 成为系统2候选
    escalate_above: float
    # 系统2（贵模型）每轮最多唤醒次数 = 全局深度算力预算，随旋钮动态调
    budget: int


# 越往下越激进：抑制线越低 → 更多信号上板；顶出线越低 → 更容易顶出；预算越高 → 越敢深想。
PRESETS = {
    "宽松": Knob("宽松", suppress_below=0.75, escalate_above=0.85, budget=1),
    "正常": Knob("正常", suppress_below=0.55, escalate_above=0.75, budget=2),
    "保守": Knob("保守", suppress_below=0.40, escalate_above=0.62, budget=3),
    "战时": Knob("战时", suppress_below=0.25, escalate_above=0.45, budget=99),
}

DEFAULT = "正常"


def get_knob(name: str) -> Knob:
    return PRESETS.get(name, PRESETS[DEFAULT])
