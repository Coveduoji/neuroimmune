import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type TermMode = 'bio' | 'sec';

// 术语字典：key → { 生物术语, 安全术语 }
const DICT: Record<string, { bio: string; sec: string }> = {
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

interface TermCtx {
  mode: TermMode;
  setMode: (m: TermMode) => void;
  t: (key: string) => string;
}

const Ctx = createContext<TermCtx>({ mode: 'bio', setMode: () => {}, t: (k) => DICT[k]?.bio ?? k });

export function TermProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<TermMode>(() => (localStorage.getItem('term_mode') === 'sec' ? 'sec' : 'bio'));
  useEffect(() => { localStorage.setItem('term_mode', mode); }, [mode]);
  const t = (key: string) => DICT[key]?.[mode] ?? key;
  return <Ctx.Provider value={{ mode, setMode, t }}>{children}</Ctx.Provider>;
}

export function useTerms() {
  return useContext(Ctx);
}
