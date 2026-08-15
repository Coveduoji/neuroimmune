import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { useTerms } from '../terms';
import type { Case } from '../types';

const PAGE_SIZE = 20;
const STATUSES = ['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'];
const VERDICTS = ['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'];

function severityOf(s: number): { label: string; cls: string } {
  if (s >= 1.0) return { label: '高', cls: 'tag up' };
  if (s >= 0.8) return { label: '中', cls: 'tag warn' };
  return { label: '低', cls: 'tag down' };
}

export default function Triage({ onOpen }: { onOpen: (id: number) => void }) {
  const { t } = useTerms();
  const [cases, setCases] = useState<Case[]>([]);
  const [total, setTotal] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState('');
  const [verdict, setVerdict] = useState('');
  const [pending, setPending] = useState(true);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const refresh = () => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (verdict) params.set('verdict', verdict);
    if (pending) params.set('pending', '1');
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String(page * PAGE_SIZE));
    api.listCases(params.toString())
      .then((r) => { setCases(r.items); setTotal(r.total); setLoaded(true); });
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, verdict, pending, page]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleSelect = (id: number) => {
    setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  };
  const toggleAll = () => {
    setSelected((s) => s.size === cases.length ? new Set() : new Set(cases.map((c) => c.id)));
  };

  const bulkFP = async () => {
    await api.bulkFalsePositive([...selected]);
    toast(`已批量标记 ${selected.size} 个案件为误报`);
    setSelected(new Set());
    refresh();
  };

  return (
    <div className="page">
      <div className="page-head">
        <h2>{t('triage')}</h2>
        <span className="sub">{total} 个案件 · 按强度排序</span>
        <div style={{ flex: 1 }} />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={pending} onChange={(e) => { setPending(e.target.checked); setPage(0); }} />
          只看待处理
        </label>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
          <option value="">全部状态</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={verdict} onChange={(e) => { setVerdict(e.target.value); setPage(0); }}>
          <option value="">全部结论</option>
          {VERDICTS.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <button className="btn danger" disabled={selected.size === 0} onClick={bulkFP}>批量标记误报（{selected.size}）</button>
      </div>

      {!loaded ? <div className="empty">加载中…</div> : cases.length === 0 ? (
        <div className="empty">没有符合条件的案件。</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 32 }}><input type="checkbox" checked={selected.size === cases.length && cases.length > 0} onChange={toggleAll} /></th>
                <th>案件</th><th>实体</th><th>严重度</th><th>状态</th><th>结论</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => {
                const sev = severityOf(c.strength);
                return (
                  <tr key={c.id} className="clickable" onClick={() => onOpen(c.id)}>
                    <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSelect(c.id)} /></td>
                    <td><code>{c.correlation_uid}</code></td>
                    <td>{c.entities.map((e) => e.value).join(' · ')}</td>
                    <td><span className={sev.cls}>{sev.label}</span></td>
                    <td><span className={`badge ${c.status === 'Closed' ? 'closed' : ''}`}>{c.status || 'New'}</span></td>
                    <td>{c.verdict || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="actions">
        <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>← 上一页</button>
        <span className="muted">第 {page + 1} / {pages} 页</span>
        <button className="btn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>下一页 →</button>
      </div>
    </div>
  );
}
