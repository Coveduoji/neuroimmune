export type TermMode = 'bio' | 'sec';

// 术语字典：key → { 生物术语, 安全术语 }
export const TERM_DICT: Record<string, { bio: string; sec: string }> = {
  dashboard: { bio: '看板', sec: '态势感知' },
  hippocampus: { bio: '海马体', sec: '关联分析' },
  triage: { bio: '分诊队列', sec: '案件队列' },
  thalamus: { bio: '丘脑', sec: '原始告警' },
  immune: { bio: '免疫', sec: '规则库' },
  immuneTitle: { bio: '免疫记忆', sec: '规则库' },
  tolerance: { bio: '免疫耐受', sec: '白名单' },
  innate: { bio: '固有免疫', sec: '检测规则' },
  settings: { bio: '设置', sec: '设置' },
  knob: { bio: '神经调质', sec: '风险等级' },
};
