import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { RequireAuth } from './guards';
import MainLayout from '../layouts/MainLayout';

// 路由级懒加载：把 @antv/g6（CaseDetail/Hippocampus）与 @ant-design/plots（Dashboard）
// 拆成独立 chunk，避免首屏加载全部图表库。
const Login = lazy(() => import('../pages/Login'));
const Dashboard = lazy(() => import('../pages/Dashboard'));
const Triage = lazy(() => import('../pages/Triage'));
const CaseDetail = lazy(() => import('../pages/CaseDetail'));
const Thalamus = lazy(() => import('../pages/Thalamus'));
const Immune = lazy(() => import('../pages/Immune'));
const Hippocampus = lazy(() => import('../pages/Hippocampus'));
const Settings = lazy(() => import('../pages/Settings'));
const Users = lazy(() => import('../pages/Users'));
const NotFound = lazy(() => import('../pages/NotFound'));

const wrap = (el: ReactNode) => (
  <Suspense fallback={<div style={{ padding: 48, textAlign: 'center' }}><Spin /></div>}>{el}</Suspense>
);

export const router = createBrowserRouter([
  { path: '/login', element: wrap(<Login />) },
  {
    path: '/',
    element: <RequireAuth />,
    children: [
      {
        element: <MainLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: wrap(<Dashboard />) },
          { path: 'hippocampus', element: wrap(<Hippocampus />) },
          { path: 'triage', element: wrap(<Triage />) },
          { path: 'thalamus', element: wrap(<Thalamus />) },
          { path: 'immune', element: wrap(<Immune />) },
          { path: 'settings', element: wrap(<Settings />) },
          { path: 'users', element: wrap(<Users />) },
          { path: 'cases/:id', element: wrap(<CaseDetail />) },
        ],
      },
    ],
  },
  { path: '*', element: wrap(<NotFound />) },
]);
