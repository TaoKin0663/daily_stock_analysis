import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthSettingsCard } from '../AuthSettingsCard';

const { refreshStatus, updateSettings, useAuthMock } = vi.hoisted(() => ({
  refreshStatus: vi.fn(),
  updateSettings: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../../hooks', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../../api/auth', () => ({
  authApi: {
    updateSettings,
  },
}));

describe('AuthSettingsCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      setupState: 'no_password',
      refreshStatus,
    });
  });

  it('sets the initial password with mandatory auth enabled', async () => {
    updateSettings.mockResolvedValue(undefined);
    refreshStatus.mockResolvedValue(undefined);

    render(<AuthSettingsCard />);

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('设置管理员密码'), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText('确认新密码'), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: '设置登录密码' }));

    await waitFor(() => {
      expect(updateSettings).toHaveBeenCalledWith(true, 'passwd6', 'passwd6', undefined);
    });
    expect(refreshStatus).toHaveBeenCalled();
    expect(await screen.findByText('初始登录密码已设置')).toBeInTheDocument();
  });

  it('does not offer an auth disable control when auth is already initialized', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      setupState: 'enabled',
      refreshStatus,
    });

    render(<AuthSettingsCard />);

    expect(screen.getByText('必须登录')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '设置登录密码' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('设置管理员密码')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('确认新密码')).not.toBeInTheDocument();
  });

  it('blocks initial setup when the new password is missing', async () => {
    render(<AuthSettingsCard />);

    fireEvent.click(screen.getByRole('button', { name: '设置登录密码' }));

    expect(await screen.findByText('设置新密码是必填项')).toBeInTheDocument();
    expect(updateSettings).not.toHaveBeenCalled();
  });
});
