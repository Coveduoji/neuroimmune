import { useState, useRef, type MouseEvent } from 'react';
import type { TrendBucket } from '../types';

// 固定坐标系（viewBox），随容器宽度等比缩放
const W = 720, H = 240;
const L = 44, R = 16, T = 16, B = 30; // 边距
const PW = W - L - R, PH = H - T - B;

function niceMax(v: number) {
  if (v <= 0) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / pow;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return m * pow;
}

function fmtTick(t: number, span: number) {
  const d = new Date(t * 1000);
  const p = (n: number) => String(n).padStart(2, '0');
  return span >= 86400 ? `${p(d.getMonth() + 1)}-${p(d.getDate())}` : `${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtFull(t: number) {
  const d = new Date(t * 1000);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function TrendChart({ buckets }: { buckets: TrendBucket[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const n = buckets.length;
  if (n === 0) return <div className="muted" style={{ padding: 24, textAlign: 'center' }}>暂无流量数据</div>;

  const span = n >= 2 ? buckets[n - 1].t - buckets[0].t : 0;
  const max = niceMax(buckets.reduce((m, b) => Math.max(m, b.total), 0));

  const x = (i: number) => L + (n <= 1 ? 0 : (i / (n - 1)) * PW);
  const y = (v: number) => T + (1 - v / max) * PH;

  const linePath = (key: 'total' | 'surfaced') =>
    buckets.map((b, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(b[key]).toFixed(1)}`).join(' ');
  const totalLine = linePath('total');
  const surfacedLine = linePath('surfaced');
  const area = `${totalLine} L${(L + PW).toFixed(1)},${(T + PH).toFixed(1)} L${L},${(T + PH).toFixed(1)} Z`;

  const tickIdx = (count: number) => (n <= 1 ? [0] : Array.from({ length: count }, (_, i) => Math.round((i * (n - 1)) / (count - 1))));
  const xTicks = tickIdx(5);
  const yTicks = [0, max / 2, max];

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const el = boxRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    setHover(Math.max(0, Math.min(n - 1, Math.round(ratio * (n - 1)))));
  };

  const hoverX = hover != null ? x(hover) : 0;
  const hoverPct = hover != null ? (hoverX / W) * 100 : 0;
  const anchor = hover === 0 ? '0%' : hover === n - 1 ? '100%' : '-50%';

  return (
    <div ref={boxRef} style={{ position: 'relative' }} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={L} y1={y(v)} x2={L + PW} y2={y(v)} stroke="var(--hairline)" strokeWidth="1" />
            <text x={L - 6} y={y(v) + 3.5} textAnchor="end" fontSize="11" fill="var(--muted)">{Math.round(v)}</text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={H - 10} textAnchor="middle" fontSize="11" fill="var(--muted)">{fmtTick(buckets[i].t, span)}</text>
        ))}

        <path d={area} fill="var(--accent)" fillOpacity="0.12" />
        <path d={surfacedLine} fill="none" stroke="var(--teal)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <path d={totalLine} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        <circle cx={x(n - 1)} cy={y(buckets[n - 1].total)} r="3" fill="var(--accent)" />
        <circle cx={x(n - 1)} cy={y(buckets[n - 1].surfaced)} r="3" fill="var(--teal)" />

        {hover != null && (
          <line x1={hoverX} y1={T} x2={hoverX} y2={T + PH} stroke="var(--ink-2)" strokeWidth="1" strokeDasharray="3 3" />
        )}
      </svg>

      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12 }}>
        <span className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--accent)', display: 'inline-block' }} />收到（全部）
        </span>
        <span className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--teal)', display: 'inline-block' }} />上板
        </span>
      </div>

      {hover != null && (
        <div style={{
          position: 'absolute', top: 0, left: `${hoverPct}%`, transform: `translateX(${anchor})`,
          background: 'var(--surface)', border: '1px solid var(--hairline)', borderRadius: 8,
          boxShadow: 'var(--shadow-lg)', padding: '6px 10px', fontSize: 12, pointerEvents: 'none',
          whiteSpace: 'nowrap', zIndex: 10,
        }}>
          <div className="muted" style={{ marginBottom: 2 }}>{fmtFull(buckets[hover].t)}</div>
          <div>收到 <b>{buckets[hover].total}</b></div>
          <div>上板 <b>{buckets[hover].surfaced}</b></div>
        </div>
      )}
    </div>
  );
}
