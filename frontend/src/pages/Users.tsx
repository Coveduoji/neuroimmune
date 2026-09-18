import { useState } from 'react';
import { Card, Table, Form, Input, Select, Button, Modal, Checkbox, Typography, Space, App, Tag } from 'antd';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth';
import { useAuthStore } from '../stores/auth.store';
import { useHasPerm } from '../hooks/useHasPerm';
import { PERMISSIONS } from '../lib/perm';
import { errMsg } from '../api/http';
import type { AuthUser } from '../types/models';

export default function Users() {
  const me = useAuthStore((s) => s.user);
  const canManage = useHasPerm('users');
  const { message, modal } = App.useApp();
  const qc = useQueryClient();

  const [permUser, setPermUser] = useState<AuthUser | null>(null);
  const [permDraft, setPermDraft] = useState<string[]>([]);
  const [resetUser, setResetUser] = useState<AuthUser | null>(null);
  const [resetPw, setResetPw] = useState('');
  const [createForm] = Form.useForm();
  const [pwdForm] = Form.useForm();

  const { data } = useQuery({
    queryKey: ['users'],
    queryFn: () => authApi.listUsers().then((r) => r.items),
    enabled: canManage,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ['users'] });

  const changePw = async (values: { old_password: string; new_password: string }) => {
    try {
      await authApi.changePassword(values.old_password, values.new_password);
      message.success('密码已修改');
      pwdForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const createUser = async (values: { username: string; password: string; role: string }) => {
    try {
      await authApi.register({ username: values.username, password: values.password, role: values.role });
      message.success(`已创建用户「${values.username}」`);
      createForm.resetFields();
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const changeRole = async (id: number, role: string) => {
    try {
      await authApi.updateUserRole(id, role);
      message.success('角色已更新');
    } catch (e) {
      message.error(errMsg(e));
    }
    refresh();
  };

  const removeUser = (id: number) => {
    modal.confirm({
      title: '确定删除该用户？',
      onOk: async () => {
        await authApi.deleteUser(id);
        message.success('已删除');
        refresh();
      },
    });
  };

  const openPerms = (u: AuthUser) => {
    setPermUser(u);
    setPermDraft(u.permissions ?? []);
  };
  const savePerms = async () => {
    if (!permUser) return;
    try {
      await authApi.updateUserPermissions(permUser.id, permDraft);
      message.success('权限已更新');
      setPermUser(null);
      refresh();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const doResetPw = async () => {
    if (!resetUser || !resetPw) return;
    try {
      await authApi.resetUserPassword(resetUser.id, resetPw);
      message.success('密码已重置');
      setResetUser(null);
      setResetPw('');
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      render: (v: string, u: AuthUser) => (
        <Space>
          <Typography.Text code>{v}</Typography.Text>
          {u.id === me?.id && <Tag>我</Tag>}
        </Space>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      width: 130,
      render: (role: string, u: AuthUser) => (
        <Select
          value={role} style={{ width: 100 }} size="small"
          onChange={(r) => changeRole(u.id, r)}
          options={[{ value: 'user', label: 'user' }, { value: 'admin', label: 'admin' }]}
        />
      ),
    },
    {
      title: '权限',
      dataIndex: 'permissions',
      render: (_: string[], u: AuthUser) =>
        u.role === 'admin' ? (
          <Typography.Text type="secondary">全部</Typography.Text>
        ) : (
          <Button size="small" onClick={() => openPerms(u)}>
            {u.permissions?.length ? `${u.permissions.length} 项` : '配置'}
          </Button>
        ),
    },
    { title: '创建时间', dataIndex: 'created_at', render: (v: string) => <Typography.Text type="secondary">{v}</Typography.Text> },
    {
      title: '操作',
      key: 'op',
      width: 180,
      render: (_: unknown, u: AuthUser) => (
        <Space>
          <Button size="small" onClick={() => { setResetUser(u); setResetPw(''); }}>重置密码</Button>
          {u.id !== me?.id && <Button size="small" danger onClick={() => removeUser(u.id)}>删除</Button>}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Typography.Title level={4}>用户</Typography.Title>

      <Space orientation="vertical" size={16} style={{ width: '100%' }}>
        <Card title="修改我的密码" size="small">
          <Form form={pwdForm} layout="inline" onFinish={changePw}>
            <Form.Item name="old_password" rules={[{ required: true, message: '请输入当前密码' }]}>
              <Input.Password placeholder="当前密码" autoComplete="current-password" />
            </Form.Item>
            <Form.Item name="new_password" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '至少 6 位' }]}>
              <Input.Password placeholder="新密码" autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit">修改</Button>
          </Form>
        </Card>

        {canManage && (
          <Card title="用户管理" size="small">
            <Form form={createForm} layout="inline" onFinish={createUser} style={{ marginBottom: 16 }}>
              <Form.Item name="username" rules={[{ required: true, message: '用户名必填' }]}>
                <Input placeholder="用户名" />
              </Form.Item>
              <Form.Item name="password" rules={[{ required: true, message: '密码必填' }]}>
                <Input.Password placeholder="密码" />
              </Form.Item>
              <Form.Item name="role" initialValue="user">
                <Select
                  style={{ width: 100 }}
                  options={[{ value: 'user', label: 'user' }, { value: 'admin', label: 'admin' }]}
                />
              </Form.Item>
              <Button type="primary" htmlType="submit">新建用户</Button>
            </Form>

            <Table<AuthUser> rowKey="id" dataSource={data ?? []} columns={columns} pagination={false} size="small" />
          </Card>
        )}
      </Space>

      <Modal
        title={`权限 · ${permUser?.username ?? ''}`} open={!!permUser}
        onCancel={() => setPermUser(null)} onOk={savePerms} okText="保存"
      >
        <Checkbox.Group
          value={permDraft}
          onChange={(v) => setPermDraft(v as string[])}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          options={Object.entries(PERMISSIONS).map(([k, desc]) => ({
            value: k,
            label: (
              <span>
                <b>{k}</b>
                <div style={{ fontSize: 12, color: '#8a8f98' }}>{desc}</div>
              </span>
            ),
          }))}
        />
      </Modal>

      <Modal
        title={`重置密码 · ${resetUser?.username ?? ''}`} open={!!resetUser}
        onCancel={() => setResetUser(null)} onOk={doResetPw} okText="重置"
      >
        <Input.Password value={resetPw} onChange={(e) => setResetPw(e.target.value)} placeholder="输入新密码" />
      </Modal>
    </div>
  );
}
