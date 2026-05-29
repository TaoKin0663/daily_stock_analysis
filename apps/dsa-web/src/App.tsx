import type React from 'react';
import { useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BacktestPage from './pages/BacktestPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import ChatPage from './pages/ChatPage';
import PaymentPage from './pages/PaymentPage';
import PortfolioPage from './pages/PortfolioPage';
import { ApiErrorAlert, Shell } from './components/common';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useAgentChatStore } from './stores/agentChatStore';
import './App.css';

const AppContent: React.FC = () => {
  const location = useLocation();
  const { loggedIn, currentUser, isLoading, loadError, refreshStatus } = useAuth();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          重试
        </button>
      </div>
    );
  }

  if (!loggedIn) {
    if (location.pathname === '/login') {
      return <LoginPage />;
    }
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  const hasPermission = (menuKey: string) => {
    if (currentUser?.isAdmin) {
      return true;
    }
    return Boolean(currentUser?.menuPermissions?.includes(menuKey));
  };

  const firstAllowedPath = [
    ['home', '/'],
    ['chat', '/chat'],
    ['portfolio', '/portfolio'],
    ['backtest', '/backtest'],
    ['payment', '/payment'],
    ['settings', '/settings'],
  ].find(([key]) => hasPermission(key))?.[1];

  const protectedElement = (menuKey: string, element: React.ReactElement) => (
    hasPermission(menuKey)
      ? element
      : firstAllowedPath
        ? <Navigate to={firstAllowedPath} replace />
        : <NotFoundPage />
  );

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={protectedElement('home', <HomePage />)} />
        <Route path="/chat" element={protectedElement('chat', <ChatPage />)} />
        <Route path="/portfolio" element={protectedElement('portfolio', <PortfolioPage />)} />
        <Route path="/backtest" element={protectedElement('backtest', <BacktestPage />)} />
        <Route path="/payment" element={protectedElement('payment', <PaymentPage />)} />
        <Route path="/settings" element={protectedElement('settings', <SettingsPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="/login" element={<LoginPage />} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
};

export default App;
