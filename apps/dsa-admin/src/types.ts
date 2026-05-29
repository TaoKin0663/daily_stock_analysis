export type Role = {
  id: number
  key: string
  name: string
  description: string
  isSystem: boolean
  menuKeys: string[]
  settingKeys: string[]
  createdAt?: string | null
  updatedAt?: string | null
}

export type User = {
  id: number
  username: string
  isAdmin: boolean
  isActive: boolean
  role: Role
  creditBalance: number
  lifetimeCredits: number
  createdAt?: string | null
  updatedAt?: string | null
}

export type MenuItem = {
  key: string
  label: string
  path: string
}

export type SettingItem = {
  key: string
  label: string
  category: string
  categoryLabel: string
  categoryOrder: number
  displayOrder: number
}

export type AuthStatus = {
  authEnabled: boolean
  loggedIn: boolean
  passwordSet?: boolean
  setupState: 'enabled' | 'no_password'
  currentUser?: {
    id: number
    username: string
    isAdmin: boolean
    accountType?: 'admin' | 'web' | 'system'
    roleKey?: string
    roleName?: string
    menuPermissions?: string[]
    settingPermissions?: string[]
  } | null
}

export type ApiError = Error & {
  status?: number
  detail?: unknown
}

export type LoginValues = {
  username: string
  password: string
  passwordConfirm?: string
}

export type RoleFormValues = {
  key?: string
  name: string
  description?: string
  menuKeys: string[]
  settingKeys: string[]
}
