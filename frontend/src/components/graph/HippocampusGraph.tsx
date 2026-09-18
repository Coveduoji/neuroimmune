import { useEffect, useRef } from 'react';
import { Graph } from '@antv/g6';
import type { HippocampusNode, HippocampusEdge } from '../../types/models';
import { ENTITY_COLORS } from '../../theme/tokens';

export type Sel =
  | { kind: 'node'; type: string; value: string }
  | { kind: 'edge'; type1: string; value1: string; type2: string; value2: string }
  | null;

const colorOf = (n: { data?: { type?: string } }) => ENTITY_COLORS[n.data?.type ?? ''] || '#888';

// 不用 G6 状态机制（状态样式函数在多次切换时传参不可靠、易变白），
// 直接显式改写每个节点/边的 style，再重绘，行为完全可控。
function applyFocus(g: Graph, focus: { nodeId?: string; edgeId?: string } | null) {
  const nodes = g.getNodeData();
  const edges = g.getEdgeData();
  const nodeUpdates: { id: string; style: Record<string, unknown> }[] = [];
  const edgeUpdates: { id: string; style: Record<string, unknown> }[] = [];

  if (!focus) {
    for (const n of nodes) {
      nodeUpdates.push({ id: n.id, style: { fill: colorOf(n), opacity: 1, stroke: '#fff', lineWidth: 1, zIndex: 0 } });
    }
    for (const e of edges) {
      if (e.id) edgeUpdates.push({ id: e.id, style: { stroke: '#999', lineWidth: 2.5, opacity: 1, zIndex: 0 } });
    }
  } else if (focus.nodeId) {
    const hood = new Set<string>([focus.nodeId]);
    for (const e of edges) {
      if (e.source === focus.nodeId) hood.add(e.target);
      if (e.target === focus.nodeId) hood.add(e.source);
    }
    for (const n of nodes) {
      if (n.id === focus.nodeId) {
        nodeUpdates.push({ id: n.id, style: { fill: colorOf(n), opacity: 1, stroke: '#111827', lineWidth: 4, zIndex: 10 } });
      } else if (hood.has(n.id)) {
        nodeUpdates.push({ id: n.id, style: { fill: colorOf(n), opacity: 1, stroke: '#fff', lineWidth: 1, zIndex: 5 } });
      } else {
        nodeUpdates.push({ id: n.id, style: { fill: colorOf(n), opacity: 0.35, stroke: '#fff', lineWidth: 1, zIndex: 1 } });
      }
    }
    for (const e of edges) {
      if (!e.id) continue;
      const on = e.source === focus.nodeId || e.target === focus.nodeId;
      edgeUpdates.push({
        id: e.id,
        style: on ? { stroke: '#2a78d6', lineWidth: 3, opacity: 1, zIndex: 5 } : { stroke: '#999', lineWidth: 2.5, opacity: 0.15, zIndex: 1 },
      });
    }
  } else if (focus.edgeId) {
    const edge = edges.find((e) => e.id === focus.edgeId);
    for (const n of nodes) {
      const on = n.id === edge?.source || n.id === edge?.target;
      nodeUpdates.push({
        id: n.id,
        style: on
          ? { fill: colorOf(n), opacity: 1, stroke: '#111827', lineWidth: 4, zIndex: 10 }
          : { fill: colorOf(n), opacity: 0.35, stroke: '#fff', lineWidth: 1, zIndex: 1 },
      });
    }
    for (const e of edges) {
      if (!e.id) continue;
      edgeUpdates.push({
        id: e.id,
        style: e.id === focus.edgeId
          ? { stroke: '#2a78d6', lineWidth: 3, opacity: 1, zIndex: 5 }
          : { stroke: '#999', lineWidth: 2.5, opacity: 0.15, zIndex: 1 },
      });
    }
  }

  g.updateNodeData(nodeUpdates);
  g.updateEdgeData(edgeUpdates);
  g.draw();
}

export default function HippocampusGraph({
  nodes,
  edges,
  onSelect,
}: {
  nodes: HippocampusNode[];
  edges: HippocampusEdge[];
  onSelect: (s: Sel) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!containerRef.current) return;
    let disposed = false;

    const g = new Graph({
      container: containerRef.current,
      data: {
        nodes: nodes.map((n) => ({
          id: `n${n.id}`,
          data: { type: n.type, value: n.value, label: n.value, degree: n.degree },
        })),
        edges: edges.map((e) => {
          const src = nodes.find((n) => n.id === e.source);
          const tgt = nodes.find((n) => n.id === e.target);
          return {
            id: `e${e.source}-${e.target}`,
            source: `n${e.source}`,
            target: `n${e.target}`,
            data: {
              sourceType: src?.type,
              sourceValue: src?.value,
              targetType: tgt?.type,
              targetValue: tgt?.value,
            },
          };
        }),
      },
      node: {
        style: {
          fill: (d) => ENTITY_COLORS[(d.data?.type as string) ?? ''] || '#888',
          size: (d) => 18 + Math.min(28, ((d.data?.degree as number) ?? 0) * 2.8),
          labelText: (d) => (d.data?.label as string) ?? '',
          labelFill: '#8a8f98',
          labelFontSize: 10,
          labelPlacement: 'bottom',
          stroke: '#fff',
          lineWidth: 1,
        },
      },
      edge: {
        style: { stroke: '#999', lineWidth: 2.5 },
      },
      layout: { type: 'force', iterations: 100 },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      autoFit: 'view',
    });

    g.on('node:click', (evt: any) => {
      const id = evt?.target?.id;
      if (!id) return;
      const d = g.getNodeData(id)?.data as { type?: string; value?: string } | undefined;
      if (!d) return;
      onSelectRef.current({ kind: 'node', type: d.type ?? '', value: d.value ?? '' });
      applyFocus(g, { nodeId: id });
    });

    g.on('edge:click', (evt: any) => {
      const id = evt?.target?.id;
      if (!id) return;
      const d = g.getEdgeData(id)?.data as
        | { sourceType?: string; sourceValue?: string; targetType?: string; targetValue?: string }
        | undefined;
      if (!d) return;
      onSelectRef.current({
        kind: 'edge',
        type1: d.sourceType ?? '', value1: d.sourceValue ?? '',
        type2: d.targetType ?? '', value2: d.targetValue ?? '',
      });
      applyFocus(g, { edgeId: id });
    });

    g.on('click', (evt: any) => {
      if (evt?.targetType === 'canvas') {
        onSelectRef.current(null);
        applyFocus(g, null);
      }
    });

    g.render().then(() => {
      if (disposed) g.destroy();
    });
    graphRef.current = g;

    return () => {
      disposed = true;
      g.destroy();
      graphRef.current = null;
    };
  }, [nodes, edges]);

  return <div ref={containerRef} style={{ width: '100%', height: 620 }} />;
}
