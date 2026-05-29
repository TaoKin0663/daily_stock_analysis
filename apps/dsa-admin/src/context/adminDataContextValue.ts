import { createContext } from 'react'
import type { ApiError, AuthStatus, LoginValues, MenuItem, Role, SettingItem, User } from '../types'

export type AdminDataContextValue = {
  authStatus: AuthStatus | null
  users: User[]
  roles: Role[]
  menus: MenuItem[]
  settings: SettingItem[]
  loading: boolean
  error: ApiError | null
  loginError: string | null
  loggingIn: boolean
  savingUserId: number | null
  isFirstTimeSetup: boolean
  shouldShowLogin: boolean
  loadData: () => Promise<void>
  handleLogin: (values: LoginValues) => Promise<void>
  handleLogout: () => Promise<void>
  assignUserRole: (user: User, roleId: number) => Promise<void>
  updateUserStatus: (user: User, isActive: boolean) => Promise<void>
}

export const AdminDataContext = createContext<AdminDataContextValue | null>(null)
