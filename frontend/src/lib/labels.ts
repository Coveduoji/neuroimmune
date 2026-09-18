// 结论（verdict）的中文显示标签。状态（status）保持英文原样显示。
export const VERDICT_LABELS: Record<string, string> = {
  'True Positive': '真阳性', 'Suspicious': '可疑', 'False Positive': '误报', 'Benign': '良性', 'Insufficient Data': '证据不足',
};

export const statusLabel = (v?: string) => v || '—';
export const verdictLabel = (v?: string) => (v && VERDICT_LABELS[v]) || v || '—';
