import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { Field } from '../components/Field';
import type { FreqConfig, GatingConfig, ModelConfig, DetectionConfig, IngestConfig, SourcesConfig, WebhookConfig } from '../types';

interface PresetVals { suppress_below: number; escalate_above: number; budget: number; }

const ALL_FIELDS = ['correlation_uid', 'title', 'strength', 'status', 'verdict', 'entities', 'ips', 'alerts',
  'report.verdict', 'report.confidence', 'report.digest', 'report.attack_chain', 'report.iocs', 'report.remediations', 'report.unknowns'];

const FIELD_GROUPS: [string, [string, string][]][] = [
  ['案件身份', [['correlation_uid', 'ID'], ['title', '标题'], ['strength', '强度'], ['status', '状态'], ['verdict', '定性']]],
  ['关联', [['entities', '实体'], ['ips', 'IP'], ['alerts', '告警']]],
  ['报告', [['report.verdict', '定性'], ['report.confidence', '置信度'], ['report.digest', '摘要'],
    ['report.attack_chain', '攻击链'], ['report.iocs', 'IOC'], ['report.remediations', '处置建议'], ['report.unknowns', '待查']]],
];

const SOURCE_SECTIONS = ['facility', 'hostname', 'tag', 'ip'] as const;

const SECTIONS = [
  { id: 'presets', label: '阈值配置（四档）' },
  { id: 'model', label: '模型接入' },
  { id: 'freq', label: '频率降级' },
  { id: 'gating', label: '前额叶 唤醒门槛' },
  { id: 'detection', label: '检测调参' },
  { id: 'ingest', label: '数据接入（syslog）' },
  { id: 'sources', label: 'syslog 来源映射' },
  { id: 'webhooks', label: '案件外发（Webhook）' },
];

function KeyValueMap({ entries, onChange, keyPh, valPh }: {
  entries: [string, string][];
  onChange: (e: [string, string][]) => void;
  keyPh: string;
  valPh: string;
}) {
  return (
    <div>
      {entries.map(([k, v], i) => (
        <div key={i} className="kv-row">
          <input value={k} placeholder={keyPh} onChange={(e) => { const n = [...entries]; n[i] = [e.target.value, v]; onChange(n); }} />
          <span className="muted">→</span>
          <input value={v} placeholder={valPh} onChange={(e) => { const n = [...entries]; n[i] = [k, e.target.value]; onChange(n); }} />
          <button className="btn" onClick={() => onChange(entries.filter((_, j) => j !== i))}>删</button>
        </div>
      ))}
      <button className="btn" onClick={() => onChange([...entries, ['', '']])}>添加</button>
    </div>
  );
}

export default function AdvancedSettings({ onBack }: { onBack: () => void }) {
  const [presets, setPresets] = useState<Record<string, PresetVals> | null>(null);
  const [edits, setEdits] = useState<Record<string, PresetVals>>({});
  const [freq, setFreqState] = useState<FreqConfig | null>(null);
  const [freqEdits, setFreqEdits] = useState<FreqConfig | null>(null);
  const [gating, setGatingState] = useState<GatingConfig | null>(null);
  const [gatingEdits, setGatingEdits] = useState<GatingConfig | null>(null);
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [detection, setDetection] = useState<DetectionConfig | null>(null);
  const [ingest, setIngest] = useState<IngestConfig | null>(null);
  const [sources, setSources] = useState<SourcesConfig | null>(null);
  const [webhooks, setWebhooks] = useState<WebhookConfig[] | null>(null);
  const [whName, setWhName] = useState('');
  const [whUrl, setWhUrl] = useState('');
  const [whTrigger, setWhTrigger] = useState('escalated');
  const [whFields, setWhFields] = useState<string[]>(ALL_FIELDS);
  const [section, setSection] = useState('presets');

  const load = () => {
    api.presets().then(setPresets);
    api.freq().then((f) => { setFreqState(f); setFreqEdits(f); });
    api.gating().then((g) => { setGatingState(g); setGatingEdits(g); });
    api.model().then(setModel);
    api.detection().then(setDetection);
    api.ingest().then(setIngest);
    api.sources().then(setSources);
    api.webhooks().then((r) => setWebhooks(r.items));
  };
  useEffect(load, []);

  const setEdit = (name: string, key: keyof PresetVals, val: number) => {
    setEdits((s) => ({ ...s, [name]: { ...(s[name] || presets![name]), [key]: val } }));
  };
  const savePreset = async (name: string) => {
    if (!edits[name]) return;
    await api.updatePreset(name, edits[name]);
    toast(`已保存「${name}」档`);
    load();
  };

  const setFreqEdit = (key: keyof FreqConfig, val: number) => setFreqEdits((s) => (s ? { ...s, [key]: val } : s));
  const saveFreq = async () => { if (!freqEdits) return; const f = await api.setFreq(freqEdits); setFreqState(f); setFreqEdits(f); toast('已保存频率降级'); };

  const setGatingEdit = (key: keyof GatingConfig, val: number) => setGatingEdits((s) => (s ? { ...s, [key]: val } : s));
  const saveGating = async () => { if (!gatingEdits) return; const g = await api.setGating(gatingEdits); setGatingState(g); setGatingEdits(g); toast('已保存前额叶 唤醒门槛'); };

  const patchModel = (k: keyof ModelConfig, v: any) => setModel((s) => (s ? { ...s, [k]: v } : s));
  const saveModel = async () => { if (!model) return; setModel(await api.setModel(model)); toast('已保存模型接入'); };

  const patchDetection = (k: keyof DetectionConfig, v: any) => setDetection((s) => (s ? { ...s, [k]: v } : s));
  const saveDetection = async () => { if (!detection) return; setDetection(await api.setDetection(detection)); toast('已保存检测调参'); };
  const setMockIndicator = (i: number, kw: string, w: number) => setDetection((s) => {
    if (!s) return s;
    const arr = [...s.mock_indicators]; arr[i] = [kw, w]; return { ...s, mock_indicators: arr };
  });
  const addMockIndicator = () => setDetection((s) => (s ? { ...s, mock_indicators: [...s.mock_indicators, ['', 0.1] as [string, number]] } : s));
  const delMockIndicator = (i: number) => setDetection((s) => (s ? { ...s, mock_indicators: s.mock_indicators.filter((_, j) => j !== i) } : s));

  const patchIngest = (k: keyof IngestConfig, v: any) => setIngest((s) => (s ? { ...s, [k]: v } : s));
  const saveIngest = async () => { if (!ingest) return; setIngest(await api.setIngest(ingest)); toast('已保存接入配置'); };

  const setSourcesSection = (section: keyof SourcesConfig, entries: [string, string][]) => setSources((s) => (s ? { ...s, [section]: Object.fromEntries(entries) } : s));
  const saveSources = async () => {
    if (!sources) return;
    const clean: SourcesConfig = { facility: {}, hostname: {}, tag: {}, ip: {} };
    for (const sec of SOURCE_SECTIONS) {
      for (const [k, v] of Object.entries(sources[sec])) {
        if (k.trim()) clean[sec][k.trim()] = v;
      }
    }
    setSources(await api.setSources(clean));
    toast('已保存来源映射');
  };

  const toggleField = (f: string) => setWhFields((s) => (s.includes(f) ? s.filter((x) => x !== f) : [...s, f]));
  const addWebhook = async () => {
    if (!whUrl) { toast('请填 URL'); return; }
    await api.addWebhook({ name: whName || 'webhook', url: whUrl, trigger: whTrigger, token: '', enabled: true, fields: whFields });
    toast('已添加外发目标');
    setWhName(''); setWhUrl(''); setWhTrigger('escalated');
    setWhFields(ALL_FIELDS);
    load();
  };
  const removeWebhook = async (i: number) => { await api.deleteWebhook(i); load(); };
  const testWebhook = async (i: number) => { const r = await api.testWebhook(i); toast(r.ok ? '测试成功' : '测试失败'); };

  return (
    <div className="page">
      <button className="btn back" onClick={onBack}>← 返回设置</button>
      <div className="page-head"><h2>高级设置</h2><span className="sub">阈值 · 模型 · 检测 · 接入 · 外发</span></div>

      <div className="settings-layout">
        <nav className="side-nav">
          {SECTIONS.map((s) => (
            <button key={s.id} className={section === s.id ? 'active' : ''} onClick={() => setSection(s.id)}>{s.label}</button>
          ))}
        </nav>

        <div className="settings-body">
          {section === 'presets' && (
            <div className="card">
              <div className="sec-label">阈值配置（四档）</div>
              <p className="muted">改这里即可，不用碰代码；改动立即影响入库和流式处理。</p>
              <table className="table">
                <thead><tr><th>档位</th><th>抑制线</th><th>顶出线</th><th>预算</th><th></th></tr></thead>
                <tbody>
                  {presets && Object.entries(presets).map(([name, p]) => {
                    const e = edits[name] || p;
                    return (
                      <tr key={name}>
                        <td><b>{name}</b></td>
                        <td><input type="number" step="0.05" value={e.suppress_below} onChange={(ev) => setEdit(name, 'suppress_below', +ev.target.value)} style={{ width: 70 }} /></td>
                        <td><input type="number" step="0.05" value={e.escalate_above} onChange={(ev) => setEdit(name, 'escalate_above', +ev.target.value)} style={{ width: 70 }} /></td>
                        <td><input type="number" value={e.budget} onChange={(ev) => setEdit(name, 'budget', +ev.target.value)} style={{ width: 60 }} /></td>
                        <td><button className="btn" onClick={() => savePreset(name)}>保存</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {section === 'model' && (
            <div className="card">
              <div className="sec-label">模型接入</div>
              <p className="muted">key 留空 = 回退 .env；key 掩码显示，输入新值才会覆盖。</p>
              {model && (
                <div className="grid g2" style={{ marginTop: 8 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div className="muted" style={{ fontWeight: 600 }}>杏仁核</div>
                    <Field label="API key"><input value={model.api_key} placeholder="••••（未改则不覆盖）" onChange={(e) => patchModel('api_key', e.target.value)} /></Field>
                    <Field label="base URL"><input value={model.base_url} onChange={(e) => patchModel('base_url', e.target.value)} /></Field>
                    <Field label="模型名"><input value={model.model} onChange={(e) => patchModel('model', e.target.value)} /></Field>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div className="muted" style={{ fontWeight: 600 }}>前额叶（深想）</div>
                    <Field label="API key"><input value={model.deep_api_key} placeholder="••••（未改则不覆盖）" onChange={(e) => patchModel('deep_api_key', e.target.value)} /></Field>
                    <Field label="base URL"><input value={model.deep_base_url} placeholder="空 = 回退杏仁核" onChange={(e) => patchModel('deep_base_url', e.target.value)} /></Field>
                    <Field label="模型名"><input value={model.deep_model} onChange={(e) => patchModel('deep_model', e.target.value)} /></Field>
                  </div>
                </div>
              )}
              <div className="field-row" style={{ marginTop: 12 }}>
                <Field label="temperature"><input type="number" step="0.1" value={model?.temperature ?? 0} onChange={(e) => patchModel('temperature', +e.target.value)} /></Field>
                <Field label="超时（秒）"><input type="number" value={model?.timeout ?? 120} onChange={(e) => patchModel('timeout', +e.target.value)} /></Field>
                <button className="btn primary" onClick={saveModel}>保存</button>
              </div>
            </div>
          )}

          {section === 'freq' && (
            <div className="card">
              <div className="sec-label">频率降级</div>
              <p className="muted">时间窗外历史同类型告警极多 → 判为业务误报并降级置信度（防刷屏误报）。</p>
              {freqEdits && (
                <div className="field-row" style={{ marginTop: 10 }}>
                  <Field label="时间窗（秒）"><input type="number" value={freqEdits.window} onChange={(e) => setFreqEdit('window', +e.target.value)} /></Field>
                  <Field label="频次阈值（次）"><input type="number" value={freqEdits.threshold} onChange={(e) => setFreqEdit('threshold', +e.target.value)} /></Field>
                  <Field label="置信度折扣（0~1）"><input type="number" step="0.05" value={freqEdits.demote} onChange={(e) => setFreqEdit('demote', +e.target.value)} /></Field>
                  <button className="btn primary" onClick={saveFreq}>保存</button>
                </div>
              )}
            </div>
          )}

          {section === 'gating' && (
            <div className="card">
              <div className="sec-label">前额叶 唤醒门槛</div>
              <p className="muted">单信号案件默认不唤醒前额叶（除非置信度 ≥ 地板值）；预算窗口内最多唤醒「预算」个不同案件。</p>
              {gatingEdits && (
                <div className="field-row" style={{ marginTop: 10 }}>
                  <Field label="单信号地板值（0~1）"><input type="number" step="0.01" value={gatingEdits.single_signal_floor} onChange={(e) => setGatingEdit('single_signal_floor', +e.target.value)} /></Field>
                  <Field label="预算窗口（秒）"><input type="number" value={gatingEdits.budget_window} onChange={(e) => setGatingEdit('budget_window', +e.target.value)} /></Field>
                  <button className="btn primary" onClick={saveGating}>保存</button>
                </div>
              )}
            </div>
          )}

          {section === 'detection' && (
            <div className="card">
              <div className="sec-label">检测调参</div>
              <p className="muted">案件强度 = 最强信号置信度 + min(封顶, 每额外告警 × 链加成)。</p>
              {detection && (
                <>
                  <div className="field-row" style={{ marginTop: 10 }}>
                    <Field label="链加成"><input type="number" step="0.05" value={detection.chain_bonus} onChange={(e) => patchDetection('chain_bonus', +e.target.value)} /></Field>
                    <Field label="封顶"><input type="number" step="0.05" value={detection.chain_cap} onChange={(e) => patchDetection('chain_cap', +e.target.value)} /></Field>
                    <Field label="重分析阈值（条）"><input type="number" value={detection.grew} onChange={(e) => patchDetection('grew', +e.target.value)} /></Field>
                    <Field label="RAG 条数"><input type="number" value={detection.rag_limit} onChange={(e) => patchDetection('rag_limit', +e.target.value)} /></Field>
                    <Field label="固有免疫 conf"><input type="number" step="0.05" value={detection.innate_conf} onChange={(e) => patchDetection('innate_conf', +e.target.value)} /></Field>
                    <Field label="放回 conf"><input type="number" step="0.05" value={detection.restore_conf} onChange={(e) => patchDetection('restore_conf', +e.target.value)} /></Field>
                  </div>
                  <div className="sec-label" style={{ marginTop: 16 }}>Mock 规则（仅 mock 模式生效）</div>
                  <p className="muted">关键词 → 权重；conf = min(ceiling, base + Σ命中权重)，未命中 = no_hit，可疑线 = cutoff。</p>
                  <div style={{ marginTop: 8 }}>
                    {detection.mock_indicators.map(([kw, w], i) => (
                      <div key={i} className="kv-row">
                        <input value={kw} placeholder="关键词" onChange={(e) => setMockIndicator(i, e.target.value, w)} />
                        <input type="number" step="0.01" value={w} onChange={(e) => setMockIndicator(i, kw, +e.target.value)} style={{ width: 90 }} />
                        <button className="btn" onClick={() => delMockIndicator(i)}>删</button>
                      </div>
                    ))}
                    <button className="btn" onClick={addMockIndicator}>添加关键词</button>
                  </div>
                  <div className="field-row" style={{ marginTop: 10 }}>
                    <Field label="base"><input type="number" step="0.01" value={detection.mock_base} onChange={(e) => patchDetection('mock_base', +e.target.value)} /></Field>
                    <Field label="ceiling"><input type="number" step="0.01" value={detection.mock_ceiling} onChange={(e) => patchDetection('mock_ceiling', +e.target.value)} /></Field>
                    <Field label="cutoff"><input type="number" step="0.01" value={detection.mock_cutoff} onChange={(e) => patchDetection('mock_cutoff', +e.target.value)} /></Field>
                    <Field label="no_hit"><input type="number" step="0.01" value={detection.mock_no_hit} onChange={(e) => patchDetection('mock_no_hit', +e.target.value)} /></Field>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <button className="btn primary" onClick={saveDetection}>保存</button>
                  </div>
                </>
              )}
            </div>
          )}

          {section === 'ingest' && (
            <div className="card">
              <div className="sec-label">数据接入（syslog）</div>
              {ingest && (
                <div className="field-row" style={{ marginTop: 10 }}>
                  <Field label="syslog 地址"><input value={ingest.syslog_bind} onChange={(e) => patchIngest('syslog_bind', e.target.value)} /></Field>
                  <Field label="syslog 端口"><input type="number" value={ingest.syslog_port} onChange={(e) => patchIngest('syslog_port', +e.target.value)} /></Field>
                  <Field label="巩固间隔（秒）"><input type="number" value={ingest.consolidate_interval} onChange={(e) => patchIngest('consolidate_interval', +e.target.value)} /></Field>
                  <Field label="API token"><input value={ingest.api_token} placeholder="••••（空 = 免鉴权）" onChange={(e) => patchIngest('api_token', e.target.value)} /></Field>
                  <button className="btn primary" onClick={saveIngest}>保存</button>
                </div>
              )}
              <p className="muted" style={{ marginTop: 8 }}>syslog 地址/端口改后需重启后端；巩固间隔与 API token 立即生效。</p>
            </div>
          )}

          {section === 'sources' && (
            <div className="card">
              <div className="sec-label">syslog 来源映射</div>
              <p className="muted">优先级 ip &gt; tag &gt; hostname &gt; facility，子串匹配；ip 可为完整地址或网段前缀（如 10.20.）。</p>
              {sources && (
                <>
                  <div className="grid g2" style={{ marginTop: 10 }}>
                    <div>
                      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>ip（来源地址）</div>
                      <KeyValueMap entries={Object.entries(sources.ip)} onChange={(e) => setSourcesSection('ip', e)} keyPh="1.2.3.4" valPh="天眼" />
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>tag</div>
                      <KeyValueMap entries={Object.entries(sources.tag)} onChange={(e) => setSourcesSection('tag', e)} keyPh="ossec" valPh="HIDS" />
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>hostname</div>
                      <KeyValueMap entries={Object.entries(sources.hostname)} onChange={(e) => setSourcesSection('hostname', e)} keyPh="tiyan" valPh="天眼" />
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>facility</div>
                      <KeyValueMap entries={Object.entries(sources.facility)} onChange={(e) => setSourcesSection('facility', e)} keyPh="local0" valPh="天眼" />
                    </div>
                  </div>
                  <button className="btn primary" onClick={saveSources} style={{ marginTop: 12 }}>保存来源映射</button>
                </>
              )}
            </div>
          )}

          {section === 'webhooks' && (
            <div className="card">
              <div className="sec-label">案件外发（Webhook）</div>
              <p className="muted">案件顶出深析后自动 POST 到这些地址，供 SOAR / SIEM / 工单 / 通知等下游消费。</p>
              {(webhooks ?? []).map((w, i) => (
                <div key={i} className="alert-item" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <code style={{ wordBreak: 'break-all' }}>{w.name} → {w.url}</code>
                    <span className="tag" style={{ marginLeft: 8 }}>{w.trigger === 'escalated' ? '顶出即推' : w.trigger === 'all' ? '全部' : '仅手动'}</span>
                  </div>
                  <button className="btn" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => testWebhook(i)}>测试</button>
                  <button className="chip-x" title="删除" onClick={() => removeWebhook(i)}>×</button>
                </div>
              ))}
              <div className="field-row" style={{ marginTop: 10 }}>
                <label className="field"><span>名称</span><input value={whName} onChange={(e) => setWhName(e.target.value)} /></label>
                <label className="field"><span>URL</span><input value={whUrl} placeholder="http://…" onChange={(e) => setWhUrl(e.target.value)} /></label>
                <label className="field"><span>触发</span>
                  <select value={whTrigger} onChange={(e) => setWhTrigger(e.target.value)}>
                    <option value="escalated">顶出即推</option>
                    <option value="all">全部</option>
                    <option value="manual">仅手动</option>
                  </select>
                </label>
                <button className="btn primary" onClick={addWebhook}>添加</button>
              </div>
              <div style={{ marginTop: 12 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>外发字段（点选）</div>
                {FIELD_GROUPS.map(([group, items]) => (
                  <div key={group} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    <span className="muted" style={{ fontSize: 12, minWidth: 48 }}>{group}</span>
                    {items.map(([f, label]) => (
                      <span key={f} className={`chip ${whFields.includes(f) ? 'chip-on' : ''}`} style={{ cursor: 'pointer' }} onClick={() => toggleField(f)}>{label}</span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
