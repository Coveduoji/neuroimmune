import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { navigate } from '../nav';
import type { CaseDetail as CaseDetailData, GraphData, Case } from '../types';
import GraphView from '../components/GraphView';
import ReportView from '../components/ReportView';

export default function CaseDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const [data, setData] = useState<CaseDetailData | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [verdict, setVerdict] = useState('');
  const [busy, setBusy] = useState(false);
  const [related, setRelated] = useState<Case[] | null>(null);
  const [note, setNote] = useState('');

  useEffect(() => {
    setRelated(null);
    api.getCase(id).then(setData);
    api.caseHippocampus(id).then(setGraph);
  }, [id]);

  const refresh = () => api.getCase(id).then(setData);

  const saveVerdict = async () => {
    if (!verdict) return;
    setBusy(true);
    if (verdict === 'False Positive') {
      if (!confirm('标记为误报：该案签名将写进免疫耐受白名单，以后同形状告警将被静默。确定？')) { setBusy(false); return; }
      const r = await api.falsePositive(id, note);
      toast(`已标记误报，记住 ${r.learned.length} 条免疫耐受规则`);
    } else if (verdict === 'True Positive') {
      if (!confirm('标记为真阳性：该案签名将写进固有免疫规则，以后同形状告警将边缘秒拦。确定？')) { setBusy(false); return; }
      const r = await api.truePositive(id, note);
      toast(`已标记真阳性，记住 ${r.learned.length} 条固有免疫规则`);
    } else {
      await api.patchCase(id, { verdict, note });
      toast('已保存结论');
    }
    await refresh();
    setBusy(false);
  };

  const markAlert = async (alertId: number, v: string) => {
    if (!confirm(v === 'False Positive' ? '把这条告警写进免疫耐受白名单？' : '把这条告警写进固有免疫规则？')) return;
    await api.alertDisposition(alertId, v);
    toast(v === 'False Positive' ? '已标记该条告警为误报' : '已标记该条告警为真阳性');
    await refresh();
  };

  const patch = async (body: object) => {
    setBusy(true);
    await api.patchCase(id, { ...body, note });
    toast('已更新');
    await refresh();
    setBusy(false);
  };

  const onNodeTap = (type: string, value: string) => {
    api.entityCases(type, value).then(setRelated);
  };

  const pushCase = async () => {
    setBusy(true);
    try {
      const r = await api.pushCase(id);
      const ok = r.results.filter((x) => x.ok).length;
      toast(`外发完成：${ok}/${r.results.length} 个目标成功`);
    } catch (e) {
      toast('外发失败：' + (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <div className="page empty">加载中…</div>;

  const { case: c, alerts, report } = data;

  return (
    <div className="page">
      <button className="btn back" onClick={onBack}>← 返回队列</button>
      <button className="btn back" onClick={() => navigate({ view: 'hippocampus' })}>在海马体查看</button>
      <div className="page-head">
        <h2><code>{c.correlation_uid}</code></h2>
        <span className="muted">强度 {c.strength.toFixed(2)} · {alerts.length} 条告警</span>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="sec-label">攻击链</div>
        {alerts.length === 0 ? <div className="muted">无告警</div> : (
          <div className="chain">
            {alerts.map((a, i) => (
              <div key={a.id} className="chain-step">
                <div className="chain-node">
                  <div className="chain-time">{a.time}</div>
                  <div className="chain-type">{a.source}/{a.type}</div>
                  <div className="chain-asset">{a.asset}</div>
                  <div className="chain-conf">conf {a.confidence?.toFixed(2)}</div>
                </div>
                {i < alerts.length - 1 && <div className="chain-arrow">→</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="detail-grid">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>告警时间线</h3>
          {alerts.map((a) => (
            <div className="alert-item" key={a.id}>
              <div className="meta">
                [{a.time}] {a.source}/{a.type} · conf {a.confidence?.toFixed(2)}
                {a.innate ? ' · 固有免疫秒拦' : ''}
                {a.verdict && <span className="tag up" style={{ marginLeft: 6 }}>{a.verdict}</span>}
              </div>
              <div className="raw">{a.raw}</div>
              <div style={{ marginTop: 4, display: 'flex', gap: 6 }}>
                <button className="btn" disabled={busy} onClick={() => markAlert(a.id, 'False Positive')}>误报</button>
                <button className="btn" disabled={busy} onClick={() => markAlert(a.id, 'True Positive')}>真阳性</button>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>实体图</h3>
          {graph ? <GraphView graph={graph} onNodeTap={onNodeTap} /> : <div className="empty">加载中…</div>}
          <div className="chips" style={{ marginTop: 8 }}>
            {c.entities.map((e, i) => (
              <span key={i} className="chip">{e.type}:{e.value}</span>
            ))}
          </div>
          <div className="muted" style={{ marginTop: 8 }}>点实体反查关联案件</div>
          {related !== null && (
            <div style={{ marginTop: 8 }}>
              <div className="muted">关联案件（{related.length}）</div>
              {related.map((rc) => (
                <div key={rc.id} className="alert-item" style={{ cursor: 'pointer' }} onClick={() => navigate({ caseId: rc.id })}>
                  <code style={{ color: 'var(--accent)' }}>{rc.correlation_uid}</code> · 强度 {rc.strength.toFixed(2)} · {rc.status || 'New'}
                </div>
              ))}
              {related.length === 0 && <div className="muted">无其他关联案件</div>}
            </div>
          )}
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>AI 调查报告</h3>
          <ReportView report={report} />
        </div>
      </div>

      <div className="card actions">
        <input type="text" placeholder="处置理由（为什么这么判）" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
        <select value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="">设置结论…</option>
          {['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'].map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </select>
        <button className="btn" disabled={!verdict || busy} onClick={saveVerdict}>保存结论</button>
        <button className="btn" disabled={busy} onClick={() => patch({ status: 'Closed' })}>关闭案件</button>
        <button className="btn" disabled={busy} onClick={pushCase}>外发</button>
        <button className="btn" onClick={() => window.open(`/api/cases/${id}/export`)}>导出报告</button>
      </div>
    </div>
  );
}
