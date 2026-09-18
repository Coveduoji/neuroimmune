import { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { ConfigProvider, App as AntApp, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { router } from './router';
import { useAuthStore } from './stores/auth.store';
import { useUiStore } from './stores/ui.store';
import { setUnauthorizedHandler } from './api/http';
import { lightTheme, darkTheme } from './theme/tokens';

export default function App() {
  const init = useAuthStore((s) => s.init);
  const logout = useAuthStore((s) => s.logout);
  const darkMode = useUiStore((s) => s.darkMode);

  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    init();
    return () => setUnauthorizedHandler(null);
  }, [init, logout]);

  const cfg = darkMode ? darkTheme : lightTheme;

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{ ...cfg, algorithm: darkMode ? theme.darkAlgorithm : theme.defaultAlgorithm }}
    >
      <AntApp>
        <RouterProvider router={router} />
      </AntApp>
    </ConfigProvider>
  );
}
