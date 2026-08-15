import { useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';

const FORMATS = [
  { value: 'docx', label: 'Word (.docx)' },
  { value: 'md', label: 'Markdown (.md)' },
  { value: 'html', label: 'HTML (.html)' },
];

function iso(d: Date) {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function ExportReport({ onClose }: { onClose: () => void }) {
  const [preset, setPreset] = useState('all');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [source, setSource] = useState('');
  const [verdict, setVerdict] = useState('');
  const [status, setStatus] = useState('');
  const [format, setFormat] = useState('html');
  const [busy, setBusy] = useState(false);

  const doExport = async () => {
    setBusy(true);
    const body: Record<string, string> = { format };
    if (preset === '24h') {
      const now = new Date();
      body.start = iso(new Date(now.getTime() - 24 * 3600 * 1000));
      body.end = iso(now);
    } else if (preset === '7d') {
      const now = new Date();
      body.start = iso(new Date(now.getTime() - 7 * 24 * 3600 * 1000));
      body.end = iso(now);
    } else if (start) {
      body.start = start;
      if (end) body.end = end;
    }
    if (source) body.source = source;
    if (verdict) body.verdict = verdict;
    if (status) body.status = status;
    try {
      await api.exportReport(body);
      toast('报告已导出');
      onClose();
    } catch (e) {
      toast('导出失败：' + (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const field = { display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--muted)' } as const;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>导出报告</h3>
          <button className="btn" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="field-row">
            <label style={field}>时间范围
              <select value={preset} onChange={(e) => setPreset(e.target.value)}>
                <option value="all">全部时间</option>
                <option value="24h">最近 24 小时</option>
                <option value="7d">最近 7 天</option>
                <option value="custom">自定义</option>
              </select>
            </label>
            {preset === 'custom' && (
              <>
                <label style={field}>起
                  <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
                </label>
                <label style={field}>止
                  <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
                </label>
              </>
            )}
          </div>

          <div className="field-row">
            <label style={field}>来源
              <input type="text" value={source} placeholder="留空 = 全部" onChange={(e) => setSource(e.target.value)} />
            </label>
            <label style={field}>定性
              <select value={verdict} onChange={(e) => setVerdict(e.target.value)}>
                <option value="">全部</option>
                {['True Positive', 'Suspicious', 'False Positive', 'Benign', 'Insufficient Data'].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
            <label style={field}>状态
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">全部</option>
                {['New', 'In Progress', 'On Hold', 'Resolved', 'Closed'].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </label>
          </div>

          <label style={field}>格式
            <div className="knobs" style={{ marginTop: 2 }}>
              {FORMATS.map((f) => (
                <div key={f.value} className={`knob ${format === f.value ? 'active' : ''}`} onClick={() => setFormat(f.value)}>
                  <div className="n">{f.label}</div>
                </div>
              ))}
            </div>
          </label>
        </div>

        <div className="modal-foot">
          <button className="btn" onClick={onClose}>取消</button>
          <button className="btn primary" disabled={busy} onClick={doExport}>{busy ? '导出中…' : '导出'}</button>
        </div>
      </div>
    </div>
  );
}
