import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { App as AntApp } from 'antd'
import { getErrorMessage, optionalRequest, requestJson } from '../api'
import { canAccessAdmin } from '../routes'
import { AdminDataContext } from './adminDataContextValue'
import type { ApiError, AuthStatus, LoginValues, MenuItem, Role, SettingItem, User } from '../types'

export function AdminDataProvider({ children }: { children: ReactNode }) {
  const { message } = AntApp.useApp()
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [menus, setMenus] = useState<MenuItem[]>([])
  const [settings, setSettings] = useState<SettingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [loggingIn, setLoggingIn] = useState(false)
  const [savingUserId, setSavingUserId] = useState<number | null>(null)

  const isFirstTimeSetup = Boolean(
    authStatus?.setupState === 'no_password' || (authStatus?.authEnabled && !authStatus.passwordSet),
  )
  const shouldShowLogin = Boolean(authStatus?.authEnabled && !authStatus.loggedIn)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const status = await requestJson<AuthStatus>('/api/v1/auth/status')
      setAuthStatus(status)

      if (status.authEnabled && !status.loggedIn) {
        setUsers([])
        setRoles([])
        setMenus([])
        setSettings([])
        return
      }

      if (!canAccessAdmin(status)) {
        setUsers([])
        setRoles([])
        setMenus([])
        setSettings([])
        return
      }

      try {
        const [menuList, settingList, roleList, userList] = await Promise.all([
          requestJson<MenuItem[]>('/api/v1/admin/menus'),
          requestJson<SettingItem[]>('/api/v1/admin/settings'),
          optionalRequest(requestJson<Role[]>('/api/v1/admin/roles'), []),
          optionalRequest(requestJson<User[]>('/api/v1/admin/users'), []),
        ])
        setMenus(menuList)
        setSettings(settingList)
        setRoles(roleList)
        setUsers(userList)
      } catch (err) {
        if ((err as ApiError).status === 401) {
          setAuthStatus({ ...status, loggedIn: false, currentUser: null })
          setUsers([])
          setRoles([])
          setMenus([])
          setSettings([])
          return
        }
        throw err
      }
    } catch (err) {
      setError(err as ApiError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadData])

  const handleLogin = useCallback(
    async (values: LoginValues) => {
      setLoginError(null)
      if (isFirstTimeSetup && values.password !== values.passwordConfirm) {
        setLoginError('两次输入的密码不一致')
        return
      }

      setLoggingIn(true)
      try {
        await requestJson<void>('/api/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            username: values.username,
            password: values.password,
            passwordConfirm: isFirstTimeSetup ? values.passwordConfirm : undefined,
          }),
        })
        message.success('登录成功')
        await loadData()
      } catch (err) {
        setLoginError(getErrorMessage(err))
      } finally {
        setLoggingIn(false)
      }
    },
    [isFirstTimeSetup, loadData, message],
  )

  const handleLogout = useCallback(async () => {
    await requestJson<void>('/api/v1/auth/logout', { method: 'POST' })
    message.success('已退出登录')
    await loadData()
  }, [loadData, message])

  const assignUserRole = useCallback(
    async (user: User, roleId: number) => {
      setSavingUserId(user.id)
      try {
        await requestJson<User>(`/api/v1/admin/users/${user.id}/role`, {
          method: 'PATCH',
          body: JSON.stringify({ roleId }),
        })
        message.success('用户角色已更新')
        await loadData()
      } catch (err) {
        message.error(getErrorMessage(err))
      } finally {
        setSavingUserId(null)
      }
    },
    [loadData, message],
  )

  const updateUserStatus = useCallback(
    async (user: User, isActive: boolean) => {
      setSavingUserId(user.id)
      try {
        await requestJson<User>(`/api/v1/admin/users/${user.id}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ isActive }),
        })
        message.success('用户状态已更新')
        await loadData()
      } catch (err) {
        message.error(getErrorMessage(err))
      } finally {
        setSavingUserId(null)
      }
    },
    [loadData, message],
  )

  const value = useMemo(
    () => ({
      authStatus,
      users,
      roles,
      menus,
      settings,
      loading,
      error,
      loginError,
      loggingIn,
      savingUserId,
      isFirstTimeSetup,
      shouldShowLogin,
      loadData,
      handleLogin,
      handleLogout,
      assignUserRole,
      updateUserStatus,
    }),
    [
      authStatus,
      users,
      roles,
      menus,
      settings,
      loading,
      error,
      loginError,
      loggingIn,
      savingUserId,
      isFirstTimeSetup,
      shouldShowLogin,
      loadData,
      handleLogin,
      handleLogout,
      assignUserRole,
      updateUserStatus,
    ],
  )

  return <AdminDataContext.Provider value={value}>{children}</AdminDataContext.Provider>
}
