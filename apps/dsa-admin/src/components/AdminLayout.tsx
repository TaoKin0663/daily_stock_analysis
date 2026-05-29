import { Button, Layout, Menu, Space, Typography, Popover } from 'antd'
import { RedoOutlined } from '@ant-design/icons';
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAdminData } from '../hooks/useAdminData'
import { ADMIN_ROUTES } from '../routes'

const { Content, Header, Sider } = Layout
const { Title, Text } = Typography

export function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { authStatus, loadData, handleLogout } = useAdminData()
  const selectedRoute = ADMIN_ROUTES.find((route) => location.pathname.startsWith(route.path)) ?? ADMIN_ROUTES[0]

  return (
    <Layout className="admin-shell">
      <Sider width={224} theme="dark">
        <div className="admin-brand">DSA Admin</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedRoute ? [selectedRoute.key] : []}
          items={ADMIN_ROUTES.map((route) => ({ key: route.key, label: route.label }))}
          onClick={(info) => {
            const nextRoute = ADMIN_ROUTES.find((route) => route.key === info.key)
            if (nextRoute) {
              void navigate(nextRoute.path)
            }
          }}
        />
      </Sider>
      <Layout>
        <Header className="admin-header !h-[auto]">
          <div>
            <Title level={4} className="admin-title">
              管理后台
            </Title>
            {/* <Text type="secondary">
              {authStatus?.currentUser
                ? `${authStatus.currentUser.username} · ${authStatus.currentUser.roleName ?? '未分配角色'}`
                : '本地免认证模式'}
            </Text> */}
          </div>
          <Space>
            {/* <Button onClick={() => void loadData()}>刷新</Button> */}
            <Button type="dashed" shape="circle" icon={<RedoOutlined />} onClick={() => void loadData()} />
            <Popover placement="bottom"
              content={
                <>
                  {authStatus?.authEnabled ? <Button color='danger' variant="filled" onClick={() => void handleLogout()}>退出</Button> : null}
                </>
              }>
              <Text type="secondary">
              {/* · ${authStatus.currentUser.roleName ?? '未分配角色'} */}
                {authStatus?.currentUser
                  ? `${authStatus.currentUser.username}`
                  : '-'}
              </Text>
            </Popover>

          </Space>
        </Header>
        <Content className="admin-content !flex-1">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
