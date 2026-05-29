import { App as AntApp, Button, Form, Input, Modal, Space, Table, Tabs, Tag, Transfer, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMemo, useState } from 'react'
import { getErrorMessage, requestJson } from '../api'
import { useAdminData } from '../hooks/useAdminData'
import { getCategoryTitle, getFieldTitle } from '../systemConfigI18n'
import type { Role, RoleFormValues, SettingItem } from '../types'

const { Title, Text } = Typography

type TransferItem = {
  key: string
  title: string
  description: string
}

type SettingCategoryGroup = {
  key: string
  title: string
  categoryOrder: number
  items: SettingItem[]
}

function mergeCategorySelection(allSelected: string[], categoryKeys: Set<string>, nextCategoryKeys: string[]) {
  const next = new Set(allSelected.filter((key) => !categoryKeys.has(key)))
  for (const key of nextCategoryKeys) {
    next.add(key)
  }
  return [...next]
}

export function RolesPage() {
  const { message } = AntApp.useApp()
  const { roles, menus, settings, loading, loadData } = useAdminData()
  const [roleModalOpen, setRoleModalOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [activeSettingCategory, setActiveSettingCategory] = useState<string>()
  const [roleForm] = Form.useForm<RoleFormValues>()
  const selectedMenuKeys = (Form.useWatch('menuKeys', roleForm) ?? []) as string[]
  const selectedSettingKeys = (Form.useWatch('settingKeys', roleForm) ?? []) as string[]

  const menuTransferItems = useMemo(
    () =>
      menus.map((item) => ({
        key: item.key,
        title: item.label,
        description: item.path,
      })),
    [menus],
  )

  const settingGroups = useMemo<SettingCategoryGroup[]>(() => {
    const groupMap = new Map<string, SettingCategoryGroup>()
    for (const item of settings) {
      const group = groupMap.get(item.category) ?? {
        key: item.category,
        title: getCategoryTitle(item.category, item.categoryLabel),
        categoryOrder: item.categoryOrder,
        items: [],
      }
      group.items.push(item)
      group.categoryOrder = Math.min(group.categoryOrder, item.categoryOrder)
      groupMap.set(item.category, group)
    }

    return [...groupMap.values()]
      .map((group) => ({
        ...group,
        items: [...group.items].sort((left, right) => {
          if (left.displayOrder !== right.displayOrder) {
            return left.displayOrder - right.displayOrder
          }
          return left.key.localeCompare(right.key)
        }),
      }))
      .sort((left, right) => {
        if (left.categoryOrder !== right.categoryOrder) {
          return left.categoryOrder - right.categoryOrder
        }
        return left.key.localeCompare(right.key)
      })
  }, [settings])

  const currentSettingCategory = activeSettingCategory ?? settingGroups[0]?.key
  const activeSettingGroup = settingGroups.find((group) => group.key === currentSettingCategory) ?? settingGroups[0]
  const activeSettingCategoryKeys = useMemo(
    () => new Set((activeSettingGroup?.items ?? []).map((item) => item.key)),
    [activeSettingGroup],
  )
  const activeSettingTransferItems = useMemo<TransferItem[]>(
    () =>
      (activeSettingGroup?.items ?? []).map((item) => ({
        key: item.key,
        title: getFieldTitle(item.key, item.label),
        description: item.key,
      })),
    [activeSettingGroup],
  )
  const activeSelectedSettingKeys = selectedSettingKeys.filter((key) => activeSettingCategoryKeys.has(key))

  const openCreateRole = () => {
    setEditingRole(null)
    roleForm.setFieldsValue({ key: '', name: '', description: '', menuKeys: [], settingKeys: [] })
    setActiveSettingCategory(settingGroups[0]?.key)
    setRoleModalOpen(true)
  }

  const openEditRole = (role: Role) => {
    setEditingRole(role)
    roleForm.setFieldsValue({
      key: role.key,
      name: role.name,
      description: role.description,
      menuKeys: role.menuKeys ?? [],
      settingKeys: role.settingKeys ?? [],
    })
    setActiveSettingCategory(settingGroups[0]?.key)
    setRoleModalOpen(true)
  }

  const saveRole = async () => {
    const values = await roleForm.validateFields()
    const payload = {
      key: values.key,
      name: values.name,
      description: values.description ?? '',
      menuKeys: values.menuKeys ?? [],
      settingKeys: values.settingKeys ?? [],
    }

    if (editingRole) {
      await requestJson<Role>(`/api/v1/admin/roles/${editingRole.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: payload.name,
          description: payload.description,
          menuKeys: payload.menuKeys,
          settingKeys: payload.settingKeys,
        }),
      })
      message.success('角色已更新')
    } else {
      await requestJson<Role>('/api/v1/admin/roles', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      message.success('角色已创建')
    }
    setRoleModalOpen(false)
    await loadData()
  }

  const deleteRole = async (role: Role) => {
    Modal.confirm({
      title: `删除角色：${role.name}`,
      content: '删除后无法恢复，已分配给用户的角色不能删除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        await requestJson<void>(`/api/v1/admin/roles/${role.id}`, { method: 'DELETE' })
        message.success('角色已删除')
        await loadData()
      },
    })
  }

  const columns: ColumnsType<Role> = [
    {
      title: '角色',
      dataIndex: 'name',
      render: (_, role) => (
        <Space direction="vertical" size={0}>
          <Space>
            <Text strong>{role.name}</Text>
            {role.isSystem ? <Tag color="blue">内置</Tag> : null}
          </Space>
          <Text type="secondary">{role.key}</Text>
        </Space>
      ),
    },
    {
      title: '说明',
      dataIndex: 'description',
      render: (value) => value || '-',
    },
    {
      title: '菜单权限',
      dataIndex: 'menuKeys',
      render: (_, role) => `${role.menuKeys.length}/${menus.length} 项`,
      width: 130,
    },
    {
      title: '设置项权限',
      dataIndex: 'settingKeys',
      render: (_, role) => `${(role.settingKeys ?? []).length}/${settings.length} 项`,
      width: 140,
    },
    {
      title: '操作',
      width: 170,
      render: (_, role) => (
        <Space>
          <Button size="small" onClick={() => openEditRole(role)}>
            编辑
          </Button>
          <Button
            size="small"
            danger
            disabled={role.isSystem}
            onClick={() => void deleteRole(role)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={roles}
        pagination={false}
        title={() => (
          <div className="table-title">
            <div>
              <Title level={5}>角色管理</Title>
              {/* <Text type="secondary">超管和普通角色为内置角色，不能删除。</Text> */}
            </div>
            <Button type="primary" onClick={openCreateRole}>
              新增角色
            </Button>
          </div>
        )}
      />

      <Modal
        title={editingRole ? `编辑角色：${editingRole.name}` : '新增角色'}
        open={roleModalOpen}
        okText="保存"
        cancelText="取消"
        width={960}
        onOk={() => void saveRole().catch((err) => message.error(getErrorMessage(err)))}
        onCancel={() => setRoleModalOpen(false)}
        destroyOnHidden
      >
        <Form form={roleForm} layout="vertical">
          <Form.Item
            label="角色 Key"
            name="key"
            rules={[{ required: true, message: '请输入角色 Key' }]}
          >
            <Input disabled={Boolean(editingRole)} placeholder="例如 operator" />
          </Form.Item>
          <Form.Item
            label="角色名称"
            name="name"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="例如 运营" />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input.TextArea rows={3} maxLength={256} />
          </Form.Item>
          <Form.Item label="菜单权限" name="menuKeys">
            <Transfer
              dataSource={menuTransferItems}
              targetKeys={selectedMenuKeys}
              titles={['未授权菜单', '已授权菜单']}
              listStyle={{ width: 390, height: 240 }}
              render={(item) => `${item.title} (${item.key})`}
              onChange={(nextTargetKeys) => {
                roleForm.setFieldValue('menuKeys', nextTargetKeys.map(String))
              }}
            />
          </Form.Item>
          <Form.Item
            label="设置项权限"
            name="settingKeys"
            extra="这里对应 C 端设置页里的具体配置项；有权限才会在设置页显示并允许保存。"
          >
            <Tabs
              activeKey={currentSettingCategory}
              onChange={setActiveSettingCategory}
              items={settingGroups.map((group) => {
                const selectedCount = group.items.filter((item) => selectedSettingKeys.includes(item.key)).length
                return {
                  key: group.key,
                  label: `${group.title} ${selectedCount}/${group.items.length}`,
                }
              })}
            />
            <Transfer
              dataSource={activeSettingTransferItems}
              targetKeys={activeSelectedSettingKeys}
              titles={['未授权设置项', '已授权设置项']}
              listStyle={{ width: 390, height: 330 }}
              showSearch
              filterOption={(inputValue, item) => {
                const text = `${item.title} ${item.description}`.toLowerCase()
                return text.includes(inputValue.toLowerCase())
              }}
              render={(item) => `${item.title} (${item.description})`}
              onChange={(nextTargetKeys) => {
                roleForm.setFieldValue(
                  'settingKeys',
                  mergeCategorySelection(selectedSettingKeys, activeSettingCategoryKeys, nextTargetKeys.map(String)),
                )
              }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
