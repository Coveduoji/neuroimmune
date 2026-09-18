import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import './styles/global.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
  },
});

// 注意：不包 StrictMode —— React 18 的 StrictMode 会让 effect 双挂载，
// G6（canvas 引擎）在双挂载下会重复初始化 + 重复跑 force 布局，导致切页/图渲染极慢。
ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </ErrorBoundary>,
);
