import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { useTerms } from '../terms';
import type { DashboardData } from '../types';

export default function Immune() {
  const { t } = useTerms();
  const [d, setD] = useState<DashboardData | null>(null);

  const load = () => { api.dashboard().then(setD); };
  useEffect(load, []);

  const removeTolerance = async (sig: string) => { await api.toleranceRemove(sig); load(); };
  const clearTolerance = async () => { if (!confirm('清空免疫耐受白名单？')) return; await api.toleranceClear(); load(); };
  const removeInnate = async (sig: string) => { await api.innateRemove(sig); load(); };
  const clearInnate = async () => { if (!confirm('清空固有免疫规则？')) return; await api.innateClear(); load(); };

  if (!d) return <div className="page empty">加载中…</div>;

  const { tolerance, innate } = d;

  return (
    <div className="page">
      <div className="page-head"><h2>{t('immuneTitle')}</h2><span className="sub">{t('tolerance')} · {t('innate')}</span></div>

      <div className="grid g2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>{t('tolerance')}（已知好 → 静默）</div>
            <button className="btn" style={{ padding: '2px 8px', fontSize: 12 }} onClick={clearTolerance}>清空</button>
          </div>
          <p className="muted" style={{ marginTop: 2 }}>按签名匹配（掩码 IP/哈希/数字）；命中即静默，连杏仁核都不叫。</p>
          <div style={{ marginTop: 10, maxHeight: 520, overflowY: 'auto' }}>
            {tolerance.map((sig, i) => (
              <div key={i} className="alert-item" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <code style={{ flex: 1, wordBreak: 'break-all', whiteSpace: 'pre-wrap', background: 'transparent', padding: 0 }}>{sig}</code>
                <button className="chip-x" title="删除" onClick={() => removeTolerance(sig)}>×</button>
              </div>
            ))}
            {tolerance.length === 0 && <div className="muted">空</div>}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div className="sec-label" style={{ marginBottom: 0 }}>{t('innate')}（已知坏 → 秒拦）</div>
            <button className="btn" style={{ padding: '2px 8px', fontSize: 12 }} onClick={clearInnate}>清空</button>
          </div>
          <p className="muted" style={{ marginTop: 2 }}>命中即边缘秒拦（conf 0.95），前额叶 不醒。</p>
          <div style={{ marginTop: 10, maxHeight: 520, overflowY: 'auto' }}>
            {innate.map((sig, i) => (
              <div key={i} className="alert-item" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <code style={{ flex: 1, wordBreak: 'break-all', whiteSpace: 'pre-wrap', background: 'transparent', padding: 0 }}>{sig}</code>
                <button className="chip-x" title="删除" onClick={() => removeInnate(sig)}>×</button>
              </div>
            ))}
            {innate.length === 0 && <div className="muted">空</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
