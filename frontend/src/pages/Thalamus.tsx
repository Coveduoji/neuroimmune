import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { navigate } from '../nav';
import { useTerms } from '../terms';
import type { RawAlert, AuditEntry } from '../types';

const PAGE = 50;

export default function Thalamus() {
  const { t } = useTerms();
  const [q, setQ] = useState('');
  const [source, setSource] = useState('');
  const [suppressed, setSuppressed] = useState(''); // '' | '0' | '1'
  const [sort, setSort] = useState<'time' | 'confidence'>('time');
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ items: RawAlert[]; total: number; sources: string[] } | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const params: Record<string, string> = { sort, limit: String(PAGE), offset: String(page * PAGE) };
    if (q.trim()) params.q = q.trim();
    if (source) params.source = source;
    if (suppressed) params.suppressed = suppressed;
    api.thalamus(params).then(setData);
  }, [q, source, suppressed, sort, page, reload]);

  const restore = async (id: number) => {
    const r = await api.restore(id);
    toast('已放回');
    setReload((x) => x + 1);
    navigate({ caseId: r.case_id });
  };

  useEffect(() => { api.audit().then((r) => setAudit(r.items)); }, []);

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="page">
      <div className="page-head">
        <h2>{t('thalamus')}</h2>
        <span className="sub">原始信号流 · {total} 条</span>
        <div className="spacer" />
        <input type="text" placeholder="搜索 raw / 主体 / 类型…" value={q}
          onChange={(e) => { setQ(e.target.value); setPage(0); }} style={{ width: 220 }} />
        <select value={source} onChange={(e) => { setSource(e.target.value); setPage(0); }}>
          <option value="">全部来源</option>
          {(data?.sources ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={suppressed} onChange={(e) => { setSuppressed(e.target.value); setPage(0); }}>
          <option value="">全部（含被抑制）</option>
          <option value="0">仅上板</option>
          <option value="1">仅被抑制</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as 'time' | 'confidence')}>
          <option value="time">按时间</option>
          <option value="confidence">按置信度</option>
        </select>
      </div>

      <div className="thalamus-grid">
        <div className="card" style={{ minWidth: 0 }}>
          {!data ? <div className="muted">加载中…</div> : data.items.length === 0 ? (
            <div className="muted">没有告警。</div>
          ) : data.items.map((a) => (
            <div key={a.id} className="alert-item" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div className="meta">
                  [{a.time}] {a.source}/{a.type} · conf {a.confidence?.toFixed(2) ?? '—'}
                  {a.suppressed ? <span className="tag" style={{ marginLeft: 6 }}>被抑制</span> : null}
                  {a.innate ? <span className="tag up" style={{ marginLeft: 6 }}>固有免疫</span> : null}
                </div>
                <div className="raw">{a.raw}</div>
                {a.suppressed && a.why ? <div className="muted" style={{ fontSize: 12 }}>原因：{a.why}</div> : null}
                {a.case_uid ? (
                  <div className="meta">案件 <code style={{ cursor: 'pointer', color: 'var(--accent)' }}
                    onClick={() => navigate({ caseId: a.case_id! })}>{a.case_uid}</code></div>
                ) : null}
              </div>
              {a.suppressed ? <button className="btn" onClick={() => restore(a.id)}>放回</button> : null}
            </div>
          ))}
          {pages > 1 && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
              <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
              <span className="muted">{page + 1} / {pages}</span>
              <button className="btn" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          )}
        </div>

        <div className="card sticky" style={{ minWidth: 0 }}>
          <div className="sec-label">决策留痕（为什么没深想 / 为什么被拦）</div>
          {!audit ? <div className="muted">加载中…</div> : audit.length === 0 ? (
            <div className="muted">暂无留痕。</div>
          ) : (
            <div style={{ maxHeight: 'calc(100vh - 150px)', overflowY: 'auto' }}>
              {audit.map((x) => (
                <div key={x.id} className="alert-item">
                  <div className="meta">[{x.created_at}] <b>{x.action}</b> · {x.entity}</div>
                  <div className="raw">{x.changes}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
