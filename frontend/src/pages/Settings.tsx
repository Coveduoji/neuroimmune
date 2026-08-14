import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import AdvancedSettings from './AdvancedSettings';
import { useTerms } from '../terms';

interface PresetVals { suppress_below: number; escalate_above: number; budget: number; }

export default function Settings() {
  const { t, mode: termMode, setMode: setTermMode } = useTerms();
  const [tab, setTab] = useState<'basic' | 'advanced'>('basic');
  const [presets, setPresets] = useState<Record<string, PresetVals> | null>(null);
  const [info, setInfo] = useState<{ syslog: { bind: string; port: number }; model: string; deep_model: string } | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [mode, setModeState] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    api.presets().then(setPresets);
    api.info().then(setInfo);
    api.health().then(setHealth);
    api.mode().then((m) => setModeState(m.mode));
  };
  useEffect(load, []);

  const goBasic = () => { setTab('basic'); load(); };

  const setKnob = (knob: string) => api.setKnob(knob).then(() => { toast(`${t('knob')}已切到「${knob}」`); load(); });

  const setMode = (m: string) => api.setMode(m).then(() => {
    setModeState(m);
    toast(m === 'mock' ? '已切到 Mock 模式（零成本）' : m === 'real' ? '已切到真实模型' : '已切到自动模式');
    load();
  });

  const upload = async (f: File) => {
    const r = await api.upload(f);
    toast(`已上传入库 ${r.ingested} 条`);
    load();
  };

  const resetDb = async () => {
    if (!confirm('确定清空所有告警 / 案件 / 报告？此操作不可撤销。')) return;
    await api.reset();
    toast('已清空数据库');
    load();
  };

  const runConsolidate = async () => {
    const r = await api.consolidate();
    toast(r.memory ? `已巩固记忆：${r.memory.slice(0, 40)}…` : '巩固完成（无数据）');
    load();
  };

  if (tab === 'advanced') return <AdvancedSettings onBack={goBasic} />;

  return (
    <div className="page">
      <div className="page-head">
        <h2>{t('settings')}</h2>
        <span className="sub">{t('knob')} · 模型模式 · 接入</span>
        <div className="spacer" />
        <button className="btn" onClick={() => setTab('advanced')}>高级设置 →</button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div className="sec-label">{t('knob')}</div>
          <div className="knobs">
            {Object.entries(presets ?? {}).map(([name, p]) => (
              <div key={name} className={`knob ${name === health?.knob ? 'active' : ''}`} onClick={() => setKnob(name)}>
                <div className="n">{name}</div>
                <div className="v">抑制 {p.suppress_below} · 顶出 {p.escalate_above} · 预算 {p.budget}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="sec-label">模型模式</div>
          <p className="muted">切换杏仁核/前额叶 用 mock 还是真实模型，免重启立即生效。</p>
          <div className="knobs">
            {[['auto', '自动：有 key 用真实模型，否则 mock'], ['real', '真实模型（DeepSeek）'], ['mock', 'Mock：零成本，演示/回归']].map(([m, label]) => (
              <div key={m} className={`knob ${mode === m ? 'active' : ''}`} onClick={() => setMode(m)}>
                <div className="n">{m === 'auto' ? '自动' : m === 'real' ? '真实' : 'Mock'}</div>
                <div className="v">{label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="sec-label">数据接入</div>
          {info && (
            <div className="muted">
              syslog 接收：UDP/TCP <code>{info.syslog.bind}:{info.syslog.port}</code><br />
              杏仁核（初筛）模型：<code>{info.model}</code> · 前额叶（深度分析）模型：<code>{info.deep_model}</code>
            </div>
          )}
          <div style={{ marginTop: 12 }}>
            <input type="file" ref={fileRef} accept=".jsonl,.json,.csv" style={{ display: 'none' }}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
            <button className="btn primary" onClick={() => fileRef.current?.click()}>上传告警文件（JSONL/JSON/CSV）</button>
          </div>
          <p className="muted" style={{ marginTop: 10 }}>也可以把 rsyslog / 网络设备转发到上面的 syslog 端口，实时接入。</p>
        </div>

        <div className="card">
          <div className="sec-label">健康状态</div>
          {health && (
            <div className="chips">
              <span className="chip">DB：{health.db.alerts} 告警 / {health.db.cases} 案件</span>
              <span className="chip">syslog：{health.syslog.listening ? '监听中' : '未启动'}</span>
              <span className="chip">{t('knob')}：{health.knob}</span>
              <span className="chip">模型：{mode ?? '…'}</span>
              {health.syslog.last_ingest && (
                <span className="chip">最近入库：{new Date(health.syslog.last_ingest * 1000).toLocaleTimeString()}</span>
              )}
            </div>
          )}
          <div style={{ marginTop: 10, display: 'flex', gap: 10 }}>
            <button className="btn" onClick={load}>刷新</button>
            <button className="btn" onClick={runConsolidate}>立即夜间巩固</button>
            <button className="btn danger" onClick={resetDb}>清空数据库</button>
          </div>
        </div>

        <div className="card">
          <div className="sec-label">界面术语</div>
          <div className="knobs">
            <div className={`knob ${termMode === 'bio' ? 'active' : ''}`} onClick={() => setTermMode('bio')}>
              <div className="n">生物术语</div>
              <div className="v">丘脑 · 海马体 · 免疫 · 神经调质</div>
            </div>
            <div className={`knob ${termMode === 'sec' ? 'active' : ''}`} onClick={() => setTermMode('sec')}>
              <div className="n">安全术语</div>
              <div className="v">原始告警 · 关联分析 · 规则库 · 风险等级</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
