import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { api } from '../api/client';
import { navigate } from '../nav';
import { useTerms } from '../terms';
import type { HippocampusData, HippocampusNode, HippocampusEdge } from '../types';

const COLORS: Record<string, string> = { asset: '#2a78d6', ip: '#eb6834', hash: '#e87ba4', domain: '#eda100' };
const TYPE_LABELS: [string, string][] = [
  ['asset', '实体（主机/账号）'],
  ['ip', 'IP 地址'],
  ['hash', '文件哈希'],
  ['domain', '域名'],
];

type Sel =
  | { kind: 'node'; type: string; value: string }
  | { kind: 'edge'; type1: string; value1: string; type2: string; value2: string }
  | null;

interface EventItem {
  id: number;
  time: string;
  source: string;
  asset: string;
  type: string;
  raw: string;
  confidence: number;
  reason: string;
  case_uid: string;
  case_id: number;
}

export default function Hippocampus({ active }: { active: boolean }) {
  const { t } = useTerms();
  const [graph, setGraph] = useState<HippocampusData | null>(null);
  const [mode, setMode] = useState<'all' | 'ip' | 'entity'>('all');
  const [sel, setSel] = useState<Sel>(null);
  const [events, setEvents] = useState<{ items: EventItem[]; total: number; sources: string[] } | null>(null);
  const [sourceFilter, setSourceFilter] = useState('');
  const [sort, setSort] = useState<'time' | 'confidence'>('time');

  const refresh = () => api.hippocampus().then(setGraph);
  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (!sel) { setEvents(null); return; }
    const params: Record<string, string> = { sort };
    if (sourceFilter) params.source = sourceFilter;
    if (sel.kind === 'node') {
      params.type = sel.type;
      params.value = sel.value;
    } else {
      params.type = sel.type1;
      params.value = sel.value1;
      params.type2 = sel.type2;
      params.value2 = sel.value2;
    }
    api.hippocampusEvents(params).then(setEvents);
  }, [sel, sourceFilter, sort]);

  const filtered = useMemo(() => {
    if (!graph) return null;
    let nodes = graph.nodes;
    if (mode === 'ip') nodes = nodes.filter((n) => n.type === 'ip');
    else if (mode === 'entity') nodes = nodes.filter((n) => n.type !== 'ip');
    const ids = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes, edges };
  }, [graph, mode]);

  return (
    <div className="page">
      <div className="page-head">
        <h2>{t('hippocampus')}</h2>
        <span className="sub">实体关联 · {graph?.nodes.length ?? 0} 实体 · {graph?.edges.length ?? 0} 关联</span>
        <div className="spacer" />
        <select value={mode} onChange={(e) => setMode(e.target.value as 'all' | 'ip' | 'entity')}>
          <option value="all">全部</option>
          <option value="ip">IP 模式</option>
          <option value="entity">实体模式</option>
        </select>
        <button className="btn" onClick={refresh}>刷新</button>
      </div>

      <div className="g-detail">
        <div className="card">
          {filtered
            ? <>
                <GraphCanvas graph={filtered} active={active} onSelect={setSel} />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
                  {TYPE_LABELS.map(([type, label]) => (
                    <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: COLORS[type] }} />
                      {label}
                    </span>
                  ))}
                </div>
              </>
            : <div className="empty">暂无图数据，先接入告警。</div>}
        </div>
        <div className="card" style={{ maxHeight: 640, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <EventsPanel sel={sel} events={events} sourceFilter={sourceFilter} setSourceFilter={setSourceFilter} sort={sort} setSort={setSort} />
        </div>
      </div>
    </div>
  );
}

function GraphCanvas({ graph, active, onSelect }: { graph: { nodes: HippocampusNode[]; edges: HippocampusEdge[] }; active: boolean; onSelect: (s: Sel) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<any>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    // 只在可见时创建 cytoscape，避免隐藏容器（0 尺寸）渲染出空白/错位
    if (!active || !ref.current) return;
    if (cyRef.current) cyRef.current.destroy();
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...graph.nodes.map((n) => ({
          data: { id: `n${n.id}`, label: n.value, type: n.type, value: n.value, cases: n.cases, degree: n.degree, color: COLORS[n.type] || '#888' },
        })),
        ...graph.edges.map((e) => {
          const src = graph.nodes.find((n) => n.id === e.source);
          const tgt = graph.nodes.find((n) => n.id === e.target);
          return {
            data: {
              id: `e${e.source}-${e.target}`, source: `n${e.source}`, target: `n${e.target}`, cases: e.cases,
              sourceType: src?.type, sourceValue: src?.value, targetType: tgt?.type, targetValue: tgt?.value,
            },
          };
        }),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            'font-size': '10px',
            color: '#0b0b0b',
            'text-valign': 'top',
            'text-margin-y': 8,
            width: 'mapData(degree, 0, 10, 18, 46)',
            height: 'mapData(degree, 0, 10, 18, 46)',
          },
        },
        { selector: 'edge', style: { 'line-color': '#999', width: 1.2, 'curve-style': 'bezier' } },
        // 聚焦高亮：点中节点→亮描边+光晕并居中放大；其余节点/边淡出，只留选中节点 + 一跳邻居
        { selector: 'node.focused', style: { 'border-width': 5, 'border-color': '#111827', 'overlay-color': '#ffd166', 'overlay-opacity': 0.3, 'z-index': 10 } },
        { selector: 'node.dimmed', style: { opacity: 0.12 } },
        { selector: 'edge.dimmed', style: { opacity: 0.05 } },
        { selector: 'edge.neighbor', style: { 'line-color': '#2a78d6', width: 2.4 } },
      ],
      layout: { name: 'cose', animate: false, padding: 40 },
    });
    cyRef.current = cy;

    const focusNode = (node: any) => {
      const hood = node.closedNeighborhood(); // 选中节点 + 邻居 + 相连边
      cy.elements().addClass('dimmed');
      hood.removeClass('dimmed').removeClass('focused').removeClass('neighbor');
      node.addClass('focused');
      hood.edges().addClass('neighbor');
      cy.animate({ center: { eles: node }, zoom: Math.max(1.8, cy.zoom()) }, { duration: 250 });
    };

    const focusEdge = (edge: any) => {
      cy.elements().addClass('dimmed');
      edge.removeClass('dimmed').addClass('neighbor');
      edge.source().removeClass('dimmed').addClass('focused');
      edge.target().removeClass('dimmed').addClass('focused');
      cy.animate({ center: { eles: edge }, zoom: Math.max(1.8, cy.zoom()) }, { duration: 250 });
    };

    const resetFocus = () => {
      cy.elements().removeClass('dimmed').removeClass('focused').removeClass('neighbor');
      cy.animate({ fit: { eles: cy.elements(), padding: 40 } }, { duration: 250 });
    };

    cy.on('tap', 'node', (evt) => {
      const d = evt.target.data();
      onSelectRef.current({ kind: 'node', type: d.type, value: d.value });
      focusNode(evt.target);
    });
    cy.on('tap', 'edge', (evt) => {
      const d = evt.target.data();
      onSelectRef.current({ kind: 'edge', type1: d.sourceType, value1: d.sourceValue, type2: d.targetType, value2: d.targetValue });
      focusEdge(evt.target);
    });
    cy.on('tap', (evt) => {
      if (evt.target === cy) resetFocus(); // 点空白处复位
    });
    return () => { if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; } };
  }, [graph, active]);

  return <div ref={ref} style={{ width: '100%', height: 620, background: '#fcfcfb' }} />;
}

function EventsPanel({ sel, events, sourceFilter, setSourceFilter, sort, setSort }: {
  sel: Sel;
  events: { items: EventItem[]; total: number; sources: string[] } | null;
  sourceFilter: string;
  setSourceFilter: (s: string) => void;
  sort: 'time' | 'confidence';
  setSort: (s: 'time' | 'confidence') => void;
}) {
  if (!sel) return <div className="muted" style={{ padding: 8 }}>点一个节点或边，查看它的全部关联事件。</div>;

  const title = sel.kind === 'node' ? sel.value : `${sel.value1} — ${sel.value2}`;

  return (
    <>
      <div style={{ padding: '4px 2px 10px' }}>
        <h3 style={{ margin: 0, fontSize: 15, wordBreak: 'break-all' }}>{title}</h3>
        {events && <div className="muted" style={{ marginTop: 2 }}>共 {events.total} 条事件</div>}
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
          <option value="">全部来源</option>
          {(events?.sources ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as 'time' | 'confidence')}>
          <option value="time">按时间</option>
          <option value="confidence">按置信度</option>
        </select>
      </div>

      <div style={{ overflowY: 'auto', flex: 1 }}>
        {!events ? <div className="muted">加载中…</div> : events.items.length === 0 ? (
          <div className="muted">没有事件。</div>
        ) : events.items.map((e) => (
          <div key={e.id} className="alert-item">
            <div className="meta">[{e.time}] {e.source}/{e.type} · conf {e.confidence?.toFixed(2)}</div>
            <div className="raw">{e.raw}</div>
            <div className="meta">案件 <code style={{ cursor: 'pointer', color: 'var(--accent)' }} onClick={() => navigate({ caseId: e.case_id })}>{e.case_uid}</code></div>
          </div>
        ))}
      </div>
    </>
  );
}
