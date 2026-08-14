import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { GraphData } from '../types';

const COLORS: Record<string, string> = {
  asset: '#2a78d6',
  ip: '#eb6834',
  hash: '#e87ba4',
  domain: '#eda100',
};

export default function GraphView({
  graph,
  onNodeTap,
}: {
  graph: GraphData;
  onNodeTap?: (type: string, value: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const tapRef = useRef(onNodeTap);
  tapRef.current = onNodeTap;

  useEffect(() => {
    if (!ref.current) return;
    const cy = cytoscape({
      container: ref.current,
      elements: [
        ...graph.nodes.map((n) => ({
          data: { id: `n${n.id}`, label: n.value, color: COLORS[n.type] || '#888', type: n.type },
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
      ],
      layout: { name: 'cose', animate: false, padding: 30 },
    });
    cy.on('tap', 'node', (evt) => {
      const n = evt.target;
      tapRef.current?.(n.data('type'), n.data('label'));
    });
    return () => cy.destroy();
  }, [graph]);

  return <div ref={ref} style={{ width: '100%', height: 320, background: '#fcfcfb' }} />;
}
