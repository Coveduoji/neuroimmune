import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Result, Spin } from 'antd';
import { useAuthStore } from '../stores/auth.store';
import { useHasPerm } from '../hooks/useHasPerm';

export function RequireAuth() {
  const { user, authReady } = useAuthStore();
  const location = useLocation();
  if (!authReady) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Outlet />;
}

export function RequirePerm({ perm }: { perm: string }) {
  const ok = useHasPerm(perm);
  if (!ok) return <Result status="403" title="403" subTitle="缺少访问权限" />;
  return <Outlet />;
}
