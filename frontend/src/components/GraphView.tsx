import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { GraphData } from '../types';

const COLORS: Record<string, string> = {
  asset: '#2a78d6',
  ip: '#eb6834',
  hash: '#e87ba4',
  domain: '#eda100',
};

const key = (type: string, value: string) => `${type}\u0000${value}`;

export default function GraphView({
  graph,
  onNodeTap,
  highlight,
}: {
  graph: GraphData;
  onNodeTap?: (type: string, value: string) => void;
  highlight?: { type: string; value: string }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const tapRef = useRef(onNodeTap);
  tapRef.current = onNodeTap;

  useEffect(() => {
    if (!ref.current) return;
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...graph.nodes.map((n) => ({
          data: { id: `n${n.id}`, label: n.value, value: n.value, color: COLORS[n.type] || '#888', type: n.type },
        })),
        ...graph.edges.map(([a, b]) => ({
          data: { id: `e${a}-${b}`, source: `n${a}`, target: `n${b}` },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            'font-size': '11px',
            color: '#0b0b0b',
            'text-valign': 'top',
            'text-margin-y': 8,
            width: 28,
            height: 28,
          },
        },
        {
          selector: 'edge',
          style: { 'line-color': '#999', width: 1.5, 'curve-style': 'bezier' },
        },
        { selector: '.dimmed', style: { opacity: 0.15 } },
        {
          selector: 'node.hl-node',
          style: { 'border-width': 3, 'border-color': '#0b0b0b' },
        },
        {
          selector: 'edge.hl-edge',
          style: { 'line-color': '#2a78d6', width: 3 },
        },
      ],
      layout: { name: 'cose', animate: false, padding: 30 },
    });
    cy.on('tap', 'node', (evt) => {
      const n = evt.target;
      tapRef.current?.(n.data('type'), n.data('label'));
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const hasHighlight = !!highlight && highlight.length > 0;
    const keys = new Set((highlight ?? []).map((e) => key(e.type, e.value)));
    cy.nodes().forEach((n) => {
      const on = !hasHighlight || keys.has(key(n.data('type'), n.data('value')));
      n.toggleClass('dimmed', !on);
      n.toggleClass('hl-node', on);
    });
    cy.edges().forEach((e) => {
      const on = !hasHighlight || (e.source().hasClass('hl-node') && e.target().hasClass('hl-node'));
      e.toggleClass('dimmed', !on);
      e.toggleClass('hl-edge', on);
    });
  }, [graph, highlight]);

  return <div ref={ref} style={{ width: '100%', height: 320, background: '#fcfcfb' }} />;
}
