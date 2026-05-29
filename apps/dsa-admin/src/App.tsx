import { Alert,Spin } from 'antd'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getErrorMessage } from './api'
import { AdminLayout } from './components/AdminLayout'
import { useAdminData } from './hooks/useAdminData'
import { LoginPage } from './pages/LoginPage'
import { RolesPage } from './pages/RolesPage'
import { SystemSettingsPage } from './pages/SystemSettingsPage'
import { UsersPage } from './pages/UsersPage'
import { canAccessAdmin, getDefaultAdminPath } from './routes'
import './App.css'

function App() {
  const { authStatus, error, loading, shouldShowLogin } = useAdminData()
  const defaultPath = getDefaultAdminPath()

  if (loading) {
    return (
      <div className="admin-loading">
        <Spin size='large'></Spin>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-error">
        <Alert type="error" showIcon title="管理后台加载失败" description={getErrorMessage(error)} />
      </div>
    )
  }

  if (shouldShowLogin) {
    return <LoginPage />
  }

  if (!canAccessAdmin(authStatus)) {
    return (
      <div className="admin-error">
        <Alert
          type="error"
          showIcon
          title="无权访问管理后台"
          description="当前账号没有管理后台访问权限，请联系系统管理员确认权限。"
        />
      </div>
    )
  }

  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<Navigate to={defaultPath} replace />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/roles" element={<RolesPage />} />
        <Route path="/settings" element={<SystemSettingsPage />} />
        <Route path="*" element={<Navigate to={defaultPath} replace />} />
      </Route>
    </Routes>
  )
}

export default App
