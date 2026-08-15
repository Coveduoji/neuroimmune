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
        <div className="login-brand"><span className="logo">🧠</span> 神经免疫 · 工作台</div>
        <div className="muted" style={{ margin: '4px 0 20px' }}>登录后进入安全运营工作台</div>
        <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
        {error && <div className="login-err">{error}</div>}
        <button className="btn primary" type="submit" disabled={busy || !username || !password}>
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  );
}
