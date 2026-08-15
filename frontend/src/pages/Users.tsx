import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { toast } from '../toast';
import { hasPerm, PERMISSIONS } from '../perm';
import type { AuthUser } from '../types';

export default function Users({ me }: { me: AuthUser }) {
  const canManage = hasPerm(me, 'users');
  const [users, setUsers] = useState<AuthUser[] | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('user');
  const [oldPw, setOldPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [permUser, setPermUser] = useState<AuthUser | null>(null);
  const [permDraft, setPermDraft] = useState<string[]>([]);

  const load = () => { if (canManage) api.listUsers().then((r) => setUsers(r.items)).catch(() => {}); };
  useEffect(load, [canManage]);

  const changePw = async () => {
    if (!oldPw || !newPw) { toast('请填写当前密码和新密码'); return; }
    try {
      await api.changePassword(oldPw, newPw);
      toast('密码已修改');
      setOldPw(''); setNewPw('');
    } catch (e) { toast((e as Error).message); }
  };

  const createUser = async () => {
    if (!username || !password) { toast('用户名和密码不能为空'); return; }
    try {
      await api.register(username, password, role);
      toast(`已创建用户「${username}」`);
      setUsername(''); setPassword('');
      load();
    } catch (e) { toast((e as Error).message); }
  };

  const changeRole = async (id: number, r: string) => {
    try {
      await api.updateUserRole(id, r);
      toast('角色已更新');
    } catch (e) { toast((e as Error).message); }
    load();
  };

  const resetPw = async (id: number) => {
    const np = window.prompt('输入新密码');
    if (!np) return;
    try {
      await api.resetUserPassword(id, np);
      toast('密码已重置');
    } catch (e) { toast((e as Error).message); }
  };

  const removeUser = async (id: number) => {
    if (!confirm('确定删除该用户？')) return;
    try {
      await api.deleteUser(id);
      toast('已删除');
      load();
    } catch (e) { toast((e as Error).message); }
  };

  const openPerms = (u: AuthUser) => { setPermUser(u); setPermDraft(u.permissions ?? []); };
  const togglePerm = (k: string) => setPermDraft((d) => (d.includes(k) ? d.filter((x) => x !== k) : [...d, k]));
  const savePerms = async () => {
    if (!permUser) return;
    try {
      await api.updateUserPermissions(permUser.id, permDraft);
      toast('权限已更新');
      setPermUser(null);
      load();
    } catch (e) { toast((e as Error).message); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <h2>用户</h2>
        <span className="sub">账号 · 密码 · 权限</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div className="sec-label">修改我的密码</div>
          <div className="field-row">
            <div className="field">
              <span>当前密码</span>
              <input type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
            </div>
            <div className="field">
              <span>新密码</span>
              <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
            </div>
            <button className="btn" onClick={changePw}>修改</button>
          </div>
        </div>

        {canManage && (
          <div className="card">
            <div className="sec-label">用户管理</div>
            <div className="field-row">
              <div className="field">
                <span>用户名</span>
                <input value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <div className="field">
                <span>密码</span>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="field">
                <span>角色</span>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <button className="btn primary" onClick={createUser}>新建用户</button>
            </div>

            <div style={{ marginTop: 16 }}>
              {users === null ? <div className="muted">加载中…</div> : users.length === 0 ? <div className="muted">暂无用户</div> : (
                <table className="table">
                  <thead>
                    <tr><th>用户名</th><th>角色</th><th>权限</th><th>创建时间</th><th style={{ textAlign: 'right' }}>操作</th></tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td><code>{u.username}</code>{u.id === me.id ? <span className="muted">（我）</span> : ''}</td>
                        <td>
                          <select value={u.role} onChange={(e) => changeRole(u.id, e.target.value)}>
                            <option value="user">user</option>
                            <option value="admin">admin</option>
                          </select>
                        </td>
                        <td>
                          {u.role === 'admin'
                            ? <span className="muted">全部</span>
                            : <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={() => openPerms(u)}>
                                {u.permissions.length ? `${u.permissions.length} 项` : '配置'}
                              </button>}
                        </td>
                        <td className="muted">{u.created_at}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn" onClick={() => resetPw(u.id)}>重置密码</button>
                          {u.id !== me.id && <button className="btn danger" style={{ marginLeft: 6 }} onClick={() => removeUser(u.id)}>删除</button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>

      {permUser && (
        <div className="modal-backdrop" onClick={() => setPermUser(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <b>权限 · {permUser.username}</b>
              <button className="chip-x" onClick={() => setPermUser(null)}>×</button>
            </div>
            <div className="modal-body">
              {Object.entries(PERMISSIONS).map(([k, desc]) => (
                <label key={k} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', cursor: 'pointer' }}>
                  <input type="checkbox" checked={permDraft.includes(k)} onChange={() => togglePerm(k)} />
                  <span>
                    <b>{k}</b>
                    <div className="muted" style={{ fontSize: 12 }}>{desc}</div>
                  </span>
                </label>
              ))}
            </div>
            <div className="modal-foot">
              <button className="btn" onClick={() => setPermUser(null)}>取消</button>
              <button className="btn primary" onClick={savePerms}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
