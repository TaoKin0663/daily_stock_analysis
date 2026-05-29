import type React from 'react';
import { useMemo, useState } from 'react';
import { authApi } from '../../api/auth';
import { getParsedApiError, isParsedApiError, type ParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { Badge, Button, Input } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

export const AuthSettingsCard: React.FC = () => {
  const { setupState, refreshStatus } = useAuth();
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const needsInitialPassword = setupState === 'no_password';
  const isDirty = Boolean(password || passwordConfirm);

  const helperText = useMemo(() => {
    if (needsInitialPassword) {
      return '系统必须登录访问，请先设置初始管理员密码。';
    }
    return '登录认证已强制启用，不能关闭。需要更新密码时，请使用下方的“修改密码”功能。';
  }, [needsInitialPassword]);

  const resetForm = () => {
    setPassword('');
    setPasswordConfirm('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!needsInitialPassword) {
      return;
    }
    if (!password) {
      setError('设置新密码是必填项');
      return;
    }
    if (password !== passwordConfirm) {
      setError('两次输入的新密码不一致');
      return;
    }

    setIsSubmitting(true);
    try {
      await authApi.updateSettings(true, password.trim(), passwordConfirm.trim(), undefined);
      await refreshStatus();
      setSuccessMessage('初始登录密码已设置');
      resetForm();
    } catch (err: unknown) {
      setError(getParsedApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="认证与登录保护"
      description="管理管理员密码认证，保护系统配置安全。"
      actions={
        <Badge variant="success" size="sm">
          必须登录
        </Badge>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface)] p-4 shadow-soft-card transition-[background-color,border-color] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface-hover)]">
          <div className="space-y-1">
            <p className="text-sm font-semibold text-foreground">管理员认证</p>
            <p className="text-xs leading-6 text-muted-text">{helperText}</p>
          </div>
        </div>

        {needsInitialPassword ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <Input
                label="设置管理员密码"
                type="password"
                allowTogglePassword
                iconType="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                disabled={isSubmitting}
                placeholder="输入新密码（至少 6 位）"
              />
            </div>
            <div className="space-y-3">
              <Input
                label="确认新密码"
                type="password"
                allowTogglePassword
                iconType="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                autoComplete="new-password"
                disabled={isSubmitting}
                placeholder="再次输入以确认"
              />
            </div>
          </div>
        ) : null}

        {error ? (
          isParsedApiError(error) ? (
            <SettingsAlert title="认证设置失败" message={error.message} variant="error" />
          ) : (
            <SettingsAlert title="认证设置失败" message={error} variant="error" />
          )
        ) : null}

        {successMessage ? (
          <SettingsAlert title="操作成功" message={successMessage} variant="success" />
        ) : null}

        {needsInitialPassword ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" variant="settings-primary" isLoading={isSubmitting} disabled={isSubmitting}>
              设置登录密码
            </Button>
            <Button
              type="button"
              variant="settings-secondary"
              onClick={() => {
                setError(null);
                setSuccessMessage(null);
                resetForm();
              }}
              disabled={isSubmitting || !isDirty}
            >
              还原
            </Button>
          </div>
        ) : null}
      </form>
    </SettingsSectionCard>
  );
};
