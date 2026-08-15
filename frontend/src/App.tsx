import { useEffect, useState } from 'react';
import Triage from './pages/Triage';
import CaseDetail from './pages/CaseDetail';
import Dashboard from './pages/Dashboard';
import Hippocampus from './pages/Hippocampus';
import Settings from './pages/Settings';
import Thalamus from './pages/Thalamus';
import Immune from './pages/Immune';
import Users from './pages/Users';
import Login from './pages/Login';
import { api, getToken, clearToken, setUnauthorizedHandler } from './api/client';
import { navigate, setNavListener, type View } from './nav';
import { useTerms } from './terms';
import type { AuthUser } from './types';

const VIEWS: readonly View[] = ['dashboard', 'hippocampus', 'triage', 'thalamus', 'immune', 'settings', 'users'];

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
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);

  // 鉴权：有 token 就校验，无效/过期退回登录；401 全局钩子清登录态
  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    if (getToken()) {
      api.me().then(setUser).catch(() => { clearToken(); setUser(null); }).finally(() => setAuthReady(true));
    } else {
      setAuthReady(true);
    }
    return () => setUnauthorizedHandler(null);
  }, []);

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

  const logout = () => { clearToken(); setUser(null); };

  if (!authReady) return <div className="page empty">加载中…</div>;
  if (!user) return <Login onLogin={setUser} />;

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
          <button className={view === 'users' ? 'active' : ''} onClick={() => go('users')}>用户</button>
        </nav>
        <div className="spacer" />
        <span className="muted" style={{ marginRight: 8, fontSize: 13 }}>{user.username}{user.role === 'admin' ? ' · 管理员' : ''}</span>
        <button className="btn" onClick={logout} style={{ marginRight: 14 }}>退出</button>
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
          <div style={{ display: view === 'settings' ? 'block' : 'none' }}><Settings user={user} /></div>
          <div style={{ display: view === 'users' ? 'block' : 'none' }}><Users me={user} /></div>
        </>
      )}
    </div>
  );
}
