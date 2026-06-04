import type React from 'react';
import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Lock, Loader2, User, UserPlus } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { Button, Input, ParticleBackground } from '../components/common';
import { SettingsAlert } from '../components/settings';
import { useAuth } from '../hooks';

const LoginPage: React.FC = () => {
  const { login, register, passwordSet, setupState } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [registerMode, setRegisterMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  const isRegistering = registerMode;
  const rawRedirect = searchParams.get('redirect') ?? '';
  const redirect = rawRedirect.startsWith('/') && !rawRedirect.startsWith('//') ? rawRedirect : '/';

  useEffect(() => {
    document.title = '登录 - DSA';
  }, []);

  useEffect(() => {
    if (setupState === 'no_password' || !passwordSet) {
      console.error('Admin password is not initialized.');
    }
  }, [passwordSet, setupState]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const usernameValue = username.trim();
    if (!usernameValue) {
      setError('用户名不能为空');
      return;
    }
    if (isRegistering && password !== passwordConfirm) {
      setError('两次输入的密码不一致');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = isRegistering
        ? await register(usernameValue, password, passwordConfirm)
        : await login(password, undefined, usernameValue);

      if (result.success) {
        navigate(redirect, { replace: true });
      } else {
        setError(result.error ?? '登录失败');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleRegisterMode = () => {
    setRegisterMode((value) => !value);
    setError(null);
    setPassword('');
    setPasswordConfirm('');
    if (!registerMode && username === 'admin') {
      setUsername('');
    }
  };

  const title = isRegistering ? '注册新用户' : '用户登录';
  const description = isRegistering
    ? '使用用户名注册独立账号，数据会与其他用户隔离。'
    : '输入用户名和密码进入工作台。';

  return (
    <div className="relative flex min-h-screen flex-col justify-center overflow-hidden bg-[var(--login-bg-main)] px-4 py-12 font-sans selection:bg-[var(--login-accent-soft)] sm:px-6 lg:px-8">
      <ParticleBackground />
      <div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,var(--login-grid-line)_1px,transparent_1px),linear-gradient(to_bottom,var(--login-grid-line)_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:var(--login-grid-mask)]" />

      <div className="relative z-10 mx-auto w-full max-w-md">
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-8 text-center"
        >
          <h2 className="text-4xl font-extrabold tracking-normal text-[var(--login-text-primary)] sm:text-5xl">
            DAILY STOCK
          </h2>
          <p className="mt-2 text-sm uppercase tracking-[0.24em] text-[var(--login-text-muted)]">
            Analysis Engine
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.35 }}
          className="relative overflow-hidden rounded-2xl border border-[var(--login-border-card)] bg-[var(--login-bg-card)]/90 p-8 shadow-2xl backdrop-blur-xl"
        >
          <div className="mb-8">
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-normal text-[var(--login-text-primary)]">
              {isRegistering ? (
                <UserPlus className="h-5 w-5 text-[var(--login-accent-text)]" />
              ) : (
                <Lock className="h-5 w-5 text-[var(--login-accent-text)]" />
              )}
              <span>{title}</span>
            </h1>
            <p className="mt-2 text-sm text-[var(--login-text-secondary)]">{description}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <Input
                id="username"
                type="text"
                appearance="login"
                iconType="none"
                label="用户名"
                placeholder="用户名"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                disabled={isSubmitting}
                autoFocus
                autoComplete="username"
              />

              <Input
                id="password"
                type="password"
                appearance="login"
                allowTogglePassword
                iconType="password"
                label="密码"
                placeholder="请输入密码"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={isSubmitting}
                autoComplete={isRegistering ? 'new-password' : 'current-password'}
              />

              {isRegistering && (
                <Input
                  id="passwordConfirm"
                  type="password"
                  appearance="login"
                  allowTogglePassword
                  iconType="password"
                  label="确认密码"
                  placeholder="再次输入密码"
                  value={passwordConfirm}
                  onChange={(event) => setPasswordConfirm(event.target.value)}
                  disabled={isSubmitting}
                  autoComplete="new-password"
                />
              )}
            </div>

            {error && (
              <SettingsAlert
                title={isRegistering ? '提交失败' : '验证未通过'}
                message={isParsedApiError(error) ? error.message : error}
                variant="error"
                className="!border-[var(--login-error-border)] !bg-[var(--login-error-bg)] !text-[var(--login-error-text)]"
              />
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="h-12 w-full rounded-xl border-0 bg-gradient-to-r from-[var(--login-brand-button-start)] to-[var(--login-brand-button-end)] font-medium text-[var(--login-button-text)] shadow-lg shadow-[0_18px_36px_hsl(214_100%_8%_/_0.24)] hover:from-[var(--login-brand-button-start-hover)] hover:to-[var(--login-brand-button-end-hover)]"
              disabled={isSubmitting}
            >
              <span className="flex items-center justify-center gap-2">
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {isSubmitting
                  ? isRegistering
                    ? '正在创建用户...'
                    : '正在登录...'
                  : isRegistering
                    ? '注册并登录'
                    : '登录'}
              </span>
            </Button>
          </form>

          <button
            type="button"
            className="mt-4 inline-flex w-full items-center justify-center gap-2 text-sm text-[var(--login-accent-text)] hover:text-[var(--login-text-primary)]"
            onClick={toggleRegisterMode}
            disabled={isSubmitting}
          >
            {isRegistering ? <User className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
            <span>{isRegistering ? '返回登录' : '注册新用户'}</span>
          </button>
        </motion.div>
      </div>
    </div>
  );
};

export default LoginPage;
