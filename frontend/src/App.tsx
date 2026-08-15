import { useEffect, useState } from 'react';
import Triage from './pages/Triage';
import CaseDetail from './pages/CaseDetail';
import Dashboard from './pages/Dashboard';
import Hippocampus from './pages/Hippocampus';
import Settings from './pages/Settings';
import Thalamus from './pages/Thalamus';
import Immune from './pages/Immune';
import { api } from './api/client';
import { navigate, setNavListener, type View } from './nav';
import { useTerms } from './terms';

const VIEWS: readonly View[] = ['dashboard', 'hippocampus', 'triage', 'thalamus', 'immune', 'settings'];

// hash 路由：#/view 或 #/view/case/<id>，刷新/前进后退后保持当前界面
function parseHash(): { view: View; caseId: number | null } {
  const parts = (location.hash || '').replace(/^#\/?/, '').split('/').filter(Boolean);
  const view = (parts[0] && (VIEWS as readonly string[]).includes(parts[0])) ? parts[0] as View : 'dashboard';
  let caseId: number | null = null;
  const ci = parts.indexOf('case');
  if (ci >= 0 && parts[ci + 1]) {
    const n = parseInt(parts[ci + 1], 10);
    if (!Number.isNaN(n)) caseId = n;
  }
  return { view, caseId };
}

function toHash(view: View, caseId: number | null): string {
  return `#/${view}${caseId != null ? `/case/${caseId}` : ''}`;
}

export default function App() {
  const { t } = useTerms();
  const [view, setView] = useState<View>(() => parseHash().view);
  const [caseId, setCaseId] = useState<number | null>(() => parseHash().caseId);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const f = () => api.health().then(setHealth).catch(() => {});
    f();
    const t = setInterval(f, 15000);
    return () => clearInterval(t);
  }, []);

  // 全局导航：任何界面都能 navigate({view}) / navigate({caseId})
  useEffect(() => {
    setNavListener((t) => {
      if (t.caseId != null) {
        setCaseId(t.caseId);
        if (t.view) setView(t.view);
      } else if (t.view) {
        setCaseId(null);
        setView(t.view);
      }
    });
    return () => setNavListener(null);
  }, []);

  // 刷新 / 前进后退 → 从 hash 还原界面
  useEffect(() => {
    const apply = () => {
      const { view: v, caseId: c } = parseHash();
      setView(v);
      setCaseId(c);
    };
    window.addEventListener('hashchange', apply);
    return () => window.removeEventListener('hashchange', apply);
  }, []);

  // 界面状态 → 写回 hash（首次加载也会规范化 URL）
  useEffect(() => {
    const target = toHash(view, caseId);
    if (location.hash !== target) location.hash = target;
  }, [view, caseId]);

  const go = (v: View) => { setCaseId(null); setView(v); };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">🧠</span>神经免疫 · 工作台</div>
        <nav>
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => go('dashboard')}>{t('dashboard')}</button>
          <button className={view === 'hippocampus' ? 'active' : ''} onClick={() => go('hippocampus')}>{t('hippocampus')}</button>
          <button className={view === 'triage' ? 'active' : ''} onClick={() => go('triage')}>{t('triage')}</button>
          <button className={view === 'thalamus' ? 'active' : ''} onClick={() => go('thalamus')}>{t('thalamus')}</button>
          <button className={view === 'immune' ? 'active' : ''} onClick={() => go('immune')}>{t('immune')}</button>
          <button className={view === 'settings' ? 'active' : ''} onClick={() => go('settings')}>{t('settings')}</button>
        </nav>
        <div className="spacer" />
        {health && (
          <div className="status-bar">
            <div className="status-item">
              <span className={`dot ${health.syslog.listening ? 'on' : ''}`} />
              {health.syslog.listening ? '值守中' : '未监听'}
            </div>
            <div className="status-item" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'dashboard' })}>{t('knob')} <b>{health.knob}</b></div>
            <div className="status-item" style={{ cursor: 'pointer' }} onClick={() => navigate({ view: 'triage' })}>案件 <b>{health.db.cases}</b></div>
          </div>
        )}
      </header>
      {caseId !== null ? (
        <CaseDetail id={caseId} onBack={() => setCaseId(null)} />
      ) : (
        <>
          <div style={{ display: view === 'triage' ? 'block' : 'none' }}><Triage onOpen={setCaseId} /></div>
          <div style={{ display: view === 'hippocampus' ? 'block' : 'none' }}><Hippocampus active={view === 'hippocampus'} /></div>
          <div style={{ display: view === 'dashboard' ? 'block' : 'none' }}><Dashboard /></div>
          <div style={{ display: view === 'thalamus' ? 'block' : 'none' }}><Thalamus /></div>
          <div style={{ display: view === 'immune' ? 'block' : 'none' }}><Immune /></div>
          <div style={{ display: view === 'settings' ? 'block' : 'none' }}><Settings /></div>
        </>
      )}
    </div>
  );
}
