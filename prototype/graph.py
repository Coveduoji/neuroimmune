"""告警图——实体为点、共现为边，用连通分量找「案件 / 攻击链」。

一条信号里的所有实体两两连边（它们共同出现在同一事件里）。传递连通后，
同一个连通分量里的实体 = 同一个案件；跨信号共享实体（哪怕 asset 不同）
也能被连起来——这才是真正的「拼链」，而不是同 asset 加分的软提示。

跑法（独立验证）：
    python3 -c "import graph, signals; g=graph.build([signals.load_signals][0]); ..."
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from artifact import Entity, extract_entities


@dataclass
class SignalNode:
    """图里一条信号对应的「边」记录：它连起了哪些实体。"""
    signal_index: int
    entities: list[Entity]


@dataclass
class Graph:
    entities: list[Entity] = field(default_factory=list)      # 有序唯一实体
    index: dict = field(default_factory=dict)                  # (type,value) -> 下标
    edges: list[tuple[int, int]] = field(default_factory=list)  # 实体下标对
    signals: list[SignalNode] = field(default_factory=list)

    def add_signal(self, signal_index: int, entities: list[Entity]) -> None:
        idxs: list[int] = []
        for e in entities:
            k = (e.type, e.value)
            if k not in self.index:
                self.index[k] = len(self.entities)
                self.entities.append(e)
            idxs.append(self.index[k])
        self.signals.append(SignalNode(signal_index, entities))
        # 同一条信号里的实体两两连边
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                self.edges.append((idxs[i], idxs[j]))

    def components(self) -> list[list[int]]:
        """并查集求连通分量，返回每个分量里的实体下标列表。"""
        n = len(self.entities)
        parent = list(range(n))
        rank = [0] * n

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            if rank[ra] < rank[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            if rank[ra] == rank[rb]:
                rank[ra] += 1

        for a, b in self.edges:
            union(a, b)

        groups: dict[int, list[int]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)
        return list(groups.values())

    def component_of_entities(self, entities: list[Entity]) -> list[Entity] | None:
        """给定一条信号的实体，返回它所属分量的全部实体（跨信号共享后的整体）。"""
        target = None
        for e in entities:
            k = (e.type, e.value)
            if k in self.index:
                target = self.index[k]
                break
        if target is None:
            return entities
        # 找 target 所在分量
        for comp in self.components():
            if target in comp:
                return [self.entities[i] for i in comp]
        return entities


def component_id(entities: list[Entity]) -> str:
    """分量的稳定 id = 排序后的实体键哈希。同分量的信号得到同一个 correlation_uid。"""
    keys = sorted(f"{e.type}:{e.value}" for e in entities)
    return hashlib.sha1(",".join(keys).encode("utf-8")).hexdigest()[:12]


def build(signals: list[dict]) -> Graph:
    """从一组信号建图。"""
    g = Graph()
    for i, sig in enumerate(signals):
        ents = extract_entities(sig)
        if ents:
            g.add_signal(i, ents)
    return g


def signal_components(g: Graph) -> list[int]:
    """返回每条信号所属的连通分量 id（-1 表示该信号没抽出实体）。

    分量 id 与 g.components() 的下标一致。
    """
    entity_comp: dict[int, int] = {}
    for cid, members in enumerate(g.components()):
        for i in members:
            entity_comp[i] = cid
    out: list[int] = []
    for sn in g.signals:
        cid = -1
        for e in sn.entities:
            k = (e.type, e.value)
            if k in g.index:
                cid = entity_comp.get(g.index[k], -1)
                break
        out.append(cid)
    return out
