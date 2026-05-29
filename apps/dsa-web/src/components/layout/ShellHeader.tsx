import type React from 'react';
import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { CreditBalanceBadge } from '../payment/CreditBalanceBadge';
// import { ThemeToggle } from '../theme/ThemeToggle';

type ShellHeaderProps = {
  collapsed: boolean;
  onToggleSidebar: () => void;
  onOpenMobileNav: () => void;
};

const TITLES: Record<string, string> = {
  '/': '首页',
  '/chat': '问股',
  '/backtest': '回测',
  '/portfolio': '持仓',
  '/payment': '积分',
  '/settings': '设置',
};

export const ShellHeader: React.FC<ShellHeaderProps> = ({
  collapsed,
  onToggleSidebar,
  onOpenMobileNav,
}) => {
  const location = useLocation();
  const { currentUser } = useAuth();
  const pageTitle = TITLES[location.pathname] ?? 'Daily Stock Analysis';

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 bg-card/70 px-4 backdrop-blur-xl sm:px-6">
      {/* Mobile menu button */}
      <button
        type="button"
        onClick={onOpenMobileNav}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/60 bg-card text-secondary-text transition-colors hover:bg-hover hover:text-foreground lg:hidden"
        aria-label="打开导航菜单"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Desktop sidebar toggle */}
      <button
        type="button"
        onClick={onToggleSidebar}
        className="hidden h-9 w-9 items-center justify-center rounded-lg bg-card text-secondary-text transition-colors hover:bg-hover hover:text-foreground lg:inline-flex"
        aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
      >
        {collapsed ? <PanelLeftOpen className="h-6 w-6" /> : <PanelLeftClose className="h-6 w-6" />}
      </button>

      {/* Page title */}
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold text-foreground">{pageTitle}</h1>
      </div>

      {/* Right side: username + theme */}
      <div className="flex items-center gap-2">
        <CreditBalanceBadge />
        {currentUser ? (
          <span className="hidden text-xs text-secondary-text sm:inline-block">
            {currentUser.username}
          </span>
        ) : null}
        {/* <ThemeToggle /> */}
      </div>
    </header>
  );
};
