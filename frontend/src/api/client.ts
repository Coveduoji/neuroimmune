const BASE = '/api';

// JWT 存 localStorage，所有请求带 Authorization: Bearer。
export const getToken = () => localStorage.getItem('neuroimmune_jwt') || '';
export const setToken = (t: string) => localStorage.setItem('neuroimmune_jwt', t);
export const clearToken = () => localStorage.removeItem('neuroimmune_jwt');

// 401（token 缺失/过期）时清 token 并通知 App 退回登录页。
let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

async function j<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string> | undefined) };
  const t = getToken();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const r = await fetch(BASE + url, { ...opts, headers });
  if (r.status === 401) {
    clearToken();
    unauthorizedHandler?.();
    throw new Error('未登录或登录已过期');
  }
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const data = await r.json();
      if (data && typeof data.detail === 'string') msg = data.detail;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  // ---- 认证 ----
  login: (username: string, password: string) =>
    j<{ token: string; user: import('../types').AuthUser }>('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) }),
  me: () => j<import('../types').AuthUser>('/auth/me'),
  changePassword: (old_password: string, new_password: string) =>
    j<{ ok: boolean }>('/auth/change-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old_password, new_password }) }),
  register: (username: string, password: string, role: string) =>
    j<import('../types').AuthUser>('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password, role }) }),
  listUsers: () => j<{ items: import('../types').AuthUser[] }>('/auth/users'),
  updateUserRole: (id: number, role: string) =>
    j<import('../types').AuthUser>(`/auth/users/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) }),
  resetUserPassword: (id: number, new_password: string) =>
    j<{ ok: boolean }>(`/auth/users/${id}/reset-password`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_password }) }),
  deleteUser: (id: number) => j<{ ok: boolean }>(`/auth/users/${id}`, { method: 'DELETE' }),
  permissions: () => j<{ items: Record<string, string> }>('/auth/permissions'),
  updateUserPermissions: (id: number, permissions: string[]) =>
    j<import('../types').AuthUser>(`/auth/users/${id}/permissions`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ permissions }) }),

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
  trend: (range = '24h') => j<import('../types').TrendData>(`/trend?range=${range}`),
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
  webhooks: () => j<{ items: import('../types').WebhookConfig[] }>('/webhooks'),
  addWebhook: (body: object) =>
    j<{ items: import('../types').WebhookConfig[] }>(`/webhooks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  updateWebhook: (index: number, body: object) =>
    j<{ items: import('../types').WebhookConfig[] }>(`/webhooks/${index}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  deleteWebhook: (index: number) =>
    j<{ items: import('../types').WebhookConfig[] }>(`/webhooks/${index}`, { method: 'DELETE' }),
  testWebhook: (index: number) => j<{ ok: boolean }>(`/webhooks/${index}/test`, { method: 'POST' }),
  pushCase: (id: number) =>
    j<{ case_id: number; results: { name: string; url: string; ok: boolean }[] }>(`/cases/${id}/push`, { method: 'POST' }),
  exportReport: async (body: object) => {
    const r = await fetch(BASE + '/report/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const blob = await r.blob();
    const disp = r.headers.get('Content-Disposition') || '';
    const m = disp.match(/filename="?([^";]+)"?/);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : 'report';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  },
  exportCase: async (id: number) => {
    const r = await fetch(BASE + `/cases/${id}/export`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} });
    if (r.status === 401) { clearToken(); unauthorizedHandler?.(); throw new Error('未登录或登录已过期'); }
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const blob = await r.blob();
    const disp = r.headers.get('Content-Disposition') || '';
    const m = disp.match(/filename="?([^";]+)"?/);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : `case_${id}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
  },
};
