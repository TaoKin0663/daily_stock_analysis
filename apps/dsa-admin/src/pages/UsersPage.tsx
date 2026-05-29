import { Select, Space, Switch, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo } from 'react'
import { useAdminData } from '../hooks/useAdminData'
import type { User } from '../types'

const { Title, Text } = Typography

function formatCredits(value: number | null | undefined) {
  return (value ?? 0).toLocaleString()
}

export function UsersPage() {
  const { users, roles, loading, savingUserId, assignUserRole, updateUserStatus } = useAdminData()
  const roleOptions = useMemo(
    () => roles.map((role) => ({ label: role.name, value: role.id })),
    [roles],
  )

  const columns: ColumnsType<User> = [
    {
      title: '用户',
      dataIndex: 'username',
      render: (_, user) => (
        <Space>
          <Text strong>{user.username}</Text>
          {user.isAdmin ? <Tag color="red">超管</Tag> : null}
        </Space>
      ),
    },
    {
      title: '角色',
      dataIndex: ['role', 'name'],
      render: (_, user) => (
        <Select
          value={user.role?.id}
          options={roleOptions}
          disabled={user.username === 'admin'}
          loading={savingUserId === user.id}
          style={{ width: 180 }}
          onChange={(roleId) => void assignUserRole(user, roleId)}
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'isActive',
      width: 120,
      render: (_, user) => (
        <Switch
          checked={user.isActive}
          checkedChildren="启用"
          unCheckedChildren="停用"
          disabled={user.username === 'admin'}
          loading={savingUserId === user.id}
          onChange={(checked) => void updateUserStatus(user, checked)}
        />
      ),
    },
    {
      title: '积分余额',
      dataIndex: 'creditBalance',
      width: 150,
      align: 'right',
      render: (_, user) => (
        <Space direction="vertical" size={0}>
          <Text strong>{formatCredits(user.creditBalance)}</Text>
          <Text type="secondary">累计 {formatCredits(user.lifetimeCredits)}</Text>
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      width: 190,
      render: (value) => value ?? '-',
    },
  ]

  return (
    <Table
      rowKey="id"
      loading={loading}
      columns={columns}
      dataSource={users}
      pagination={false}
      title={() => (
        <Space className="table-title">
          <Title level={5}>用户管理</Title>
          {/* <Text type="secondary">新注册用户默认绑定普通角色</Text> */}
        </Space>
      )}
    />
  )
}
