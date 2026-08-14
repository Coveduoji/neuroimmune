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

export default function App() {
  const { t } = useTerms();
  const [view, setView] = useState<View>('dashboard');
  const [caseId, setCaseId] = useState<number | null>(null);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const f = () => api.health().then(setHealth).catch(() => {});
    f();
    const t = setInterval(f, 5000);
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

  if (caseId !== null) {
    return <CaseDetail id={caseId} onBack={() => setCaseId(null)} />;
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">🧠</span>神经免疫 · 工作台</div>
        <nav>
          <button className={view === 'dashboard' ? 'active' : ''} onClick={() => setView('dashboard')}>{t('dashboard')}</button>
          <button className={view === 'hippocampus' ? 'active' : ''} onClick={() => setView('hippocampus')}>{t('hippocampus')}</button>
          <button className={view === 'triage' ? 'active' : ''} onClick={() => setView('triage')}>{t('triage')}</button>
          <button className={view === 'thalamus' ? 'active' : ''} onClick={() => setView('thalamus')}>{t('thalamus')}</button>
          <button className={view === 'immune' ? 'active' : ''} onClick={() => setView('immune')}>{t('immune')}</button>
          <button className={view === 'settings' ? 'active' : ''} onClick={() => setView('settings')}>{t('settings')}</button>
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
      <div style={{ display: view === 'triage' ? 'block' : 'none' }}><Triage onOpen={setCaseId} /></div>
      <div style={{ display: view === 'hippocampus' ? 'block' : 'none' }}><Hippocampus active={view === 'hippocampus'} /></div>
      <div style={{ display: view === 'dashboard' ? 'block' : 'none' }}><Dashboard /></div>
      <div style={{ display: view === 'thalamus' ? 'block' : 'none' }}><Thalamus /></div>
      <div style={{ display: view === 'immune' ? 'block' : 'none' }}><Immune /></div>
      <div style={{ display: view === 'settings' ? 'block' : 'none' }}><Settings /></div>
    </div>
  );
}
