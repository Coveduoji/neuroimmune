import { useState, type FormEvent } from 'react';
import { api, setToken } from '../api/client';
import type { AuthUser } from '../types';

export default function Login({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    setBusy(true);
    setError('');
    try {
      const r = await api.login(username, password);
      setToken(r.token);
      onLogin(r.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="login-logo">🧠</span>
          <div>
            <div className="login-title">神经免疫</div>
            <div className="login-sub">安全运营工作台 · 登录</div>
          </div>
        </div>

        <div className="login-fields">
          <label className="field">
            <span>用户名</span>
            <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名" autoComplete="username" />
          </label>
          <label className="field">
            <span>密码</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码" autoComplete="current-password" />
          </label>
        </div>

        {error && <div className="login-err">{error}</div>}
        <button className="btn primary login-btn" type="submit" disabled={busy || !username || !password}>
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  );
}
