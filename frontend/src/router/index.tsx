import { createBrowserRouter, Navigate } from 'react-router-dom';
import { RequireAuth } from './guards';
import MainLayout from '../layouts/MainLayout';
import Login from '../pages/Login';
import Dashboard from '../pages/Dashboard';
import Triage from '../pages/Triage';
import CaseDetail from '../pages/CaseDetail';
import Thalamus from '../pages/Thalamus';
import Immune from '../pages/Immune';
import Hippocampus from '../pages/Hippocampus';
import Settings from '../pages/Settings';
import Users from '../pages/Users';
import NotFound from '../pages/NotFound';

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  {
    path: '/',
    element: <RequireAuth />,
    children: [
      {
        element: <MainLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: <Dashboard /> },
          { path: 'hippocampus', element: <Hippocampus /> },
          { path: 'triage', element: <Triage /> },
          { path: 'thalamus', element: <Thalamus /> },
          { path: 'immune', element: <Immune /> },
          { path: 'settings', element: <Settings /> },
          { path: 'users', element: <Users /> },
          { path: 'cases/:id', element: <CaseDetail /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFound /> },
]);
