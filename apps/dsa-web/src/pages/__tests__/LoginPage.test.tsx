import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from '../LoginPage';

const { navigate, useSearchParamsMock, useAuthMock } = vi.hoisted(() => ({
  navigate: vi.fn(),
  useSearchParamsMock: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
    useSearchParams: () => useSearchParamsMock(),
  };
});

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.documentElement.className = 'light';
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fsettings')]);
  });

  it('logs admin initialization error without showing setup form', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const login = vi.fn();
    useAuthMock.mockReturnValue({
      login,
      register: vi.fn(),
      passwordSet: false,
      setupState: 'no_password',
    });

    render(<LoginPage />);

    expect(consoleError).toHaveBeenCalledWith(
      'Admin password is not initialized. Please initialize it from dsa-admin.'
    );
    expect(screen.getByRole('heading', { name: '用户登录' })).toBeInTheDocument();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.queryByText('设置管理员密码')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('管理员密码')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('确认密码')).not.toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();

    consoleError.mockRestore();
  });

  it('navigates to redirect after a successful login', async () => {
    const login = vi.fn().mockResolvedValue({ success: true });
    useAuthMock.mockReturnValue({
      login,
      register: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'alice' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: '登录' }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/settings', { replace: true }));
    expect(login).toHaveBeenCalledWith('passwd6', undefined, 'alice');
    expect(screen.getByLabelText('密码')).toHaveAttribute('data-appearance', 'login');
  });

  it('does not override login theme tokens inline so light mode can take effect', () => {
    useAuthMock.mockReturnValue({
      login: vi.fn(),
      register: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    const { container } = render(<LoginPage />);
    const pageRoot = container.firstElementChild as HTMLElement | null;

    expect(pageRoot).not.toBeNull();
    expect(pageRoot?.getAttribute('style') ?? '').not.toContain('--login-bg-main');
  });
});
