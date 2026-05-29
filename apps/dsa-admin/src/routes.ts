import type { AuthStatus } from './types'

export type AdminRoute = {
  key: string
  label: string
  path: string
}

export const ADMIN_ROUTES: AdminRoute[] = [
  { key: 'users', label: '用户管理', path: '/users' },
  { key: 'roles', label: '角色管理', path: '/roles' },
  { key: 'settings', label: '系统设置', path: '/settings' },
]

export function getDefaultAdminPath(): string {
  return ADMIN_ROUTES[0].path
}

export function canAccessAdmin(status: AuthStatus | null): boolean {
  if (!status) {
    return false
  }
  return Boolean(status.currentUser?.isAdmin || status.currentUser?.roleKey === 'super_admin')
}
