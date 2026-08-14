const BASE = '/api';

// 若浏览器 localStorage 存了 token，则所有请求带上；后端设了 NEUROIMMUNE_API_TOKEN 时才校验。
const token = () => localStorage.getItem('neuroimmune_token') || '';

async function j<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> | undefined) };
  if (token()) headers['X-API-Token'] = token();
  const r = await fetch(BASE + url, { ...opts, headers });
  if (!r.ok) {
    const msg = r.status === 401 ? '未授权（token 缺失或错误）' : `${r.status} ${r.statusText}`;
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  listCases: (query = '') => j<{ items: import('../types').Case[]; total: number }>(`/cases${query ? `?${query}` : ''}`),
  getCase: (id: number) => j<import('../types').CaseDetail>(`/cases/${id}`),
  caseHippocampus: (id: number) => j<import('../types').GraphData>(`/cases/${id}/hippocampus`),
  patchCase: (id: number, body: object) =>
    j(`/cases/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  falsePositive: (id: number, reason = '') =>
    j<{ learned: [string, string][] }>(`/cases/${id}/false-positive`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) }),
  truePositive: (id: number, reason = '') =>
    j<{ learned: [string, string][] }>(`/cases/${id}/true-positive`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason }) }),
  bulkFalsePositive: (caseIds: number[]) =>
    j<{ learned: [string, string][] }>(`/cases/bulk-false-positive`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ case_ids: caseIds }) }),
  alertDisposition: (alertId: number, verdict: string) =>
    j(`/alerts/${alertId}/disposition`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ verdict }) }),
  dashboard: () => j<import('../types').DashboardData>('/dashboard'),
  setKnob: (knob: string) =>
    j(`/knob`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ knob }) }),
  suppressed: () => j<any[]>('/suppressed'),
  thalamus: (params: Record<string, string>) =>
    j<{ items: import('../types').RawAlert[]; total: number; sources: string[] }>(`/thalamus?` + new URLSearchParams(params).toString()),
  audit: () => j<{ items: import('../types').AuditEntry[] }>('/audit'),
  entityCases: (type: string, value: string) =>
    j<import('../types').Case[]>(`/entities/cases?type=${encodeURIComponent(type)}&value=${encodeURIComponent(value)}`),
  restore: (id: number) => j<{ case_id: number; correlation_uid: string }>(`/suppressed/${id}/restore`, { method: 'POST' }),
  hippocampus: () => j<import('../types').HippocampusData>('/hippocampus'),
  hippocampusEvents: (params: Record<string, string>) =>
    j<{ items: any[]; total: number; sources: string[] }>(`/hippocampus/events?` + new URLSearchParams(params).toString()),
  presets: () => j<Record<string, { suppress_below: number; escalate_above: number; budget: number }>>('/presets'),
  updatePreset: (name: string, body: object) =>
    j(`/presets/${name}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  freq: () => j<import('../types').FreqConfig>('/freq'),
  setFreq: (body: object) =>
    j<import('../types').FreqConfig>(`/freq`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  mode: () => j<{ mode: string }>('/mode'),
  setMode: (mode: string) =>
    j<{ mode: string }>(`/mode`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) }),
  gating: () => j<import('../types').GatingConfig>('/gating'),
  setGating: (body: object) =>
    j<import('../types').GatingConfig>(`/gating`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  model: () => j<import('../types').ModelConfig>('/model'),
  setModel: (body: object) =>
    j<import('../types').ModelConfig>(`/model`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  detection: () => j<import('../types').DetectionConfig>('/detection'),
  setDetection: (body: object) =>
    j<import('../types').DetectionConfig>(`/detection`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  ingest: () => j<import('../types').IngestConfig>('/ingest'),
  setIngest: (body: object) =>
    j<import('../types').IngestConfig>(`/ingest`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  sources: () => j<import('../types').SourcesConfig>('/sources'),
  setSources: (body: object) =>
    j<import('../types').SourcesConfig>(`/sources`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  toleranceRemove: (signature: string) =>
    j(`/tolerance/remove`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ signature }) }),
  toleranceClear: () => j(`/tolerance/clear`, { method: 'POST' }),
  innateRemove: (signature: string) =>
    j(`/innate/remove`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ signature }) }),
  innateClear: () => j(`/innate/clear`, { method: 'POST' }),
  reset: () => j<{ status: string }>('/reset', { method: 'POST' }),
  consolidate: () => j<{ status: string; memory: string | null }>('/consolidate', { method: 'POST' }),
  info: () => j<{ syslog: { bind: string; port: number }; model: string; deep_model: string }>('/info'),
  health: () => j<any>('/health'),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return j<{ ingested: number }>('/ingest/upload', { method: 'POST', body: fd });
  },
};
