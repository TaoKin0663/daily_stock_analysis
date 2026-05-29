import React, { useState } from 'react';
import { createAvatar } from '@dicebear/core';
import { identicon } from '@dicebear/collection';
import { Button, Popover } from '@heroui/react';
import { motion } from 'motion/react';
import { BarChart3, BriefcaseBusiness, Coins, Home, LogOut, MessageSquareQuote, Settings2, Unplug } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAccount, useDisconnect } from 'wagmi';
import { useAuth } from '../../contexts/AuthContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { StatusDot } from '../common/StatusDot';
import { ThemeToggle } from '../theme/ThemeToggle';

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

type NavItem = {
  key: string;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: 'completion';
  permission?: string;
};

const NAV_ITEMS: NavItem[] = [
  { key: 'home', label: '首页', to: '/', icon: Home, exact: true, permission: 'home' },
  { key: 'chat', label: '问股', to: '/chat', icon: MessageSquareQuote, badge: 'completion', permission: 'chat' },
  { key: 'portfolio', label: '持仓', to: '/portfolio', icon: BriefcaseBusiness, permission: 'portfolio' },
  { key: 'backtest', label: '回测', to: '/backtest', icon: BarChart3, permission: 'backtest' },
  { key: 'payment', label: '积分', to: '/payment', icon: Coins, permission: 'payment' },
  { key: 'settings', label: '设置', to: '/settings', icon: Settings2, permission: 'settings' },
];

function formatAddress(address: string): string {
  return `${address.slice(0, 6)}****${address.slice(-4)}`;
}

export const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed = false, onNavigate }) => {
  const { currentUser, logout } = useAuth();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const { address, chain, isConnected } = useAccount();
  const { disconnect } = useDisconnect();

  const walletAvatar = React.useMemo(() => {
    if (!address) return '';
    return createAvatar(identicon, {
      seed: address,
      size: 64,
      backgroundColor: ['f8fafc'],
    }).toDataUri();
  }, [address]);

  const shortAddress = address ? formatAddress(address) : '';
  const permissions = new Set(currentUser?.menuPermissions ?? []);
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (currentUser?.isAdmin) {
      return true;
    }
    return !item.permission || permissions.has(item.permission);
  });

  return (
    <div className="flex h-full flex-col">
      <div className={cn('flex items-center gap-3 px-3 py-4', collapsed && 'justify-center px-2')}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-cyan-600 text-white shadow-[0_8px_20px_rgba(0,212,255,0.3)]">
          <BarChart3 className="h-5 w-5" />
        </div>
        {!collapsed ? (
          <span className="truncate text-sm font-bold text-foreground">DSA</span>
        ) : null}
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2" aria-label="主导航">
        {visibleItems.map(({ key, label, to, icon: Icon, exact, badge }) => (
          <NavLink
            key={key}
            to={to}
            end={exact}
            onClick={onNavigate}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all',
                collapsed && 'justify-center px-2',
                isActive
                  ? 'bg-primary/10 text-[hsl(var(--primary))] font-medium'
                  : 'text-secondary-text hover:bg-hover hover:text-foreground'
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="activeIndicator"
                    className="absolute inset-y-1.5 left-1.5 w-0.5 rounded-full bg-[hsl(var(--primary))]"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  />
                )}
                <Icon className={cn('h-5 w-5 shrink-0', isActive && 'text-[hsl(var(--primary))]')} />
                {!collapsed ? <span className="truncate">{label}</span> : null}
                {badge === 'completion' && completionBadge ? (
                  <StatusDot
                    tone="info"
                    data-testid="chat-completion-badge"
                    className={cn(
                      'absolute right-2 border-2 border-card',
                      collapsed && 'right-1 top-1'
                    )}
                    aria-label="问股有新消息"
                  />
                ) : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 px-2 pb-4">
        <div className={cn('flex', collapsed ? 'justify-center' : 'px-3')}>
          <ThemeToggle variant="nav" collapsed={collapsed} />
        </div>

        {isConnected && address ? (
          <Popover>
            <Popover.Trigger
              className={cn(
                'flex h-10 w-full cursor-pointer select-none items-center gap-3 rounded-lg px-3 text-sm text-secondary-text transition-all hover:bg-hover hover:text-foreground',
                collapsed && 'justify-center px-2'
              )}
            >
              <img src={walletAvatar} alt="" className="h-7 w-7 shrink-0 rounded-full" />
              {!collapsed ? <span className="truncate font-medium">{shortAddress}</span> : null}
            </Popover.Trigger>
            <Popover.Content
              placement="right"
              offset={4}
            >
              <Popover.Dialog className="w-56 space-y-3 p-3">
                <div className="flex items-center gap-3">
                  <img src={walletAvatar} alt="" className="h-9 w-9 rounded-full" />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-foreground">{shortAddress}</div>
                    <div className="mt-0.5 truncate text-xs text-default-500">{chain?.name ?? 'Sepolia'}</div>
                  </div>
                </div>
                <Button
                  fullWidth
                  className="h-9 justify-start"
                  variant="danger-soft"
                  onPress={() => {
                    disconnect();
                  }}
                >
                  <Unplug className="h-4 w-4" />
                  断开连接
                </Button>
              </Popover.Dialog>
            </Popover.Content>
          </Popover>
        ) : null}

        <button
          type="button"
          onClick={() => setShowLogoutConfirm(true)}
          className={cn(
            'flex h-9 w-full cursor-pointer select-none items-center gap-3 rounded-lg px-3 text-sm text-secondary-text transition-all hover:bg-hover hover:text-foreground',
            collapsed && 'justify-center px-2'
          )}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed ? <span>退出</span> : null}
        </button>
      </div>

      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title="退出登录"
        message="确认退出当前登录状态吗？退出后需要重新输入密码。"
        confirmText="确认退出"
        cancelText="取消"
        isDanger
        onConfirm={() => {
          setShowLogoutConfirm(false);
          onNavigate?.();
          void logout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </div>
  );
};
