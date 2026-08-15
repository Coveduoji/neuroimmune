import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { navigate } from '../nav';
import { useTerms } from '../terms';
import ExportReport from '../components/ExportReport';
import TrendChart from '../components/TrendChart';
import type { DashboardData, TrendData } from '../types';

export default function Dashboard() {
  const { t } = useTerms();
  const [d, setD] = useState<DashboardData | null>(null);
  const [trend, setTrend] = useState<TrendData | null>(null);
  const [trendRange, setTrendRange] = useState('24h');
  const [showExport, setShowExport] = useState(false);

  useEffect(() => {
    const load = () => { api.dashboard().then(setD); };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const loadTrend = () => { api.trend(trendRange).then(setTrend); };
    loadTrend();
    const t = setInterval(loadTrend, 15000);
    return () => clearInterval(t);
  }, [trendRange]);

  if (!d) return <div className="page empty">加载中…</div>;

  const { counts, tolerance, innate } = d;
  const total = Math.max(1, counts.alerts);
  const denoise = counts.alerts > 0 ? Math.round((counts.alerts - counts.reports) / counts.alerts * 100) : 0;

  return (
    <div className="page">
      <div className="page-head">
        <h2>{t('dashboard')}</h2>
        <div className="spacer" />
        <button className="btn primary" onClick={() => setShowExport(true)}>导出报告</button>
      </div>

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'triage' })}><div className="v">{counts.cases}</div><div className="k">案件</div><div className="d">已归案</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'thalamus' })}><div className="v">{counts.alerts}</div><div className="k">告警</div><div className="d">上板 {counts.surfaced} · 抑制 {counts.suppressed}</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'thalamus' })}><div className="v">{counts.suppressed}</div><div className="k">被抑制</div><div className="d">留痕可研判</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'triage' })}><div className="v">{counts.reports}</div><div className="k">深度分析</div><div className="d">唤醒 {counts.reports} 次</div></div>
      </div>

      <div className="grid g4" style={{ marginBottom: 16 }}>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'hippocampus' })}><div className="v">{counts.artifacts}</div><div className="k">实体</div><div className="d">图节点</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'triage' })}><div className="v">{counts.attack_chains}</div><div className="k">攻击链</div><div className="d">已拼链</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'immune' })}><div className="v">{tolerance.length}</div><div className="k">{t('tolerance')}</div><div className="d">白名单</div></div>
        <div className="card kpi" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'immune' })}><div className="v">{innate.length}</div><div className="k">{t('innate')}</div><div className="d">规则</div></div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="sec-label">告警降噪</div>
        <div className="kpi" style={{ marginBottom: 10 }}>
          <div className="v">{denoise}%</div>
          <div className="k">降噪率</div>
          <div className="d">{counts.alerts} 条告警 → {counts.reports} 条需深度分析</div>
        </div>
        <div className="funnel">
          <div className="frow"><div className="lbl">告警</div><div className="track"><div className="fill" style={{ width: '100%' }} /></div><div className="count">{counts.alerts}</div></div>
          <div className="frow"><div className="lbl">归案</div><div className="track"><div className="fill" style={{ width: `${Math.round(counts.cases / total * 100)}%` }} /></div><div className="count">{counts.cases}</div></div>
          <div className="frow"><div className="lbl">深度分析</div><div className="track"><div className="fill teal" style={{ width: `${Math.round(counts.reports / total * 100)}%` }} /></div><div className="count">{counts.reports}</div></div>
        </div>
        <p className="muted" style={{ marginTop: 10 }}>把 {counts.alerts} 条告警聚合为 {counts.cases} 个案件，仅 {counts.reports} 个需要深度分析。</p>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div className="sec-label" style={{ marginBottom: 0 }}>流量趋势</div>
          <div className="spacer" />
          <div className="subnav">
            {[['24h', '近24小时'], ['7d', '近7天'], ['30d', '近30天']].map(([r, label]) => (
              <button key={r} className={trendRange === r ? 'active' : ''} onClick={() => setTrendRange(r)}>{label}</button>
            ))}
          </div>
        </div>
        {trend && <TrendChart buckets={trend.buckets} />}
      </div>
      {showExport && <ExportReport onClose={() => setShowExport(false)} />}
    </div>
  );
}
