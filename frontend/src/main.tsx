import ReactDOM from 'react-dom/client';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import Toaster from './components/Toaster';
import { TermProvider } from './terms';
import './index.css';

// 注意：不包 StrictMode —— React 18 的 StrictMode 会让 effect 双挂载，
// Cytoscape 在双挂载下经常渲染出空白图（已知坑）。
ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <TermProvider>
      <App />
    </TermProvider>
    <Toaster />
  </ErrorBoundary>,
);
