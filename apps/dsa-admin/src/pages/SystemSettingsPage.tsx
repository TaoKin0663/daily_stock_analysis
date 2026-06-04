import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Spin, Switch, Tabs, Tag, TimePicker, Tooltip, Typography, message } from 'antd'
import dayjs from 'dayjs'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { requestJson } from '../api'
import { getCategoryTitle, getFieldTitle } from '../systemConfigI18n'

const { Text, Title } = Typography

type FieldSchema = {
  key: string
  title?: string
  description?: string
  category: string
  data_type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'json' | 'time'
  ui_control: 'text' | 'password' | 'number' | 'select' | 'textarea' | 'switch' | 'time' | 'custom'
  is_sensitive: boolean
  is_required: boolean
  is_editable: boolean
  options: Array<string | { label: string; value: string }>
  display_order: number
  access_level?: 'admin' | 'user'
}

type ConfigItem = {
  key: string
  value: string
  raw_value_exists: boolean
  is_masked: boolean
  schema?: FieldSchema
}

type ConfigResponse = {
  config_version: string
  mask_token: string
  items: ConfigItem[]
}

type UpdateResponse = {
  success: boolean
  config_version: string
  updated_keys: string[]
  warnings: string[]
}

type AgentModelDeployment = {
  deployment_id: string
  model: string
  provider: string
  source: string
  api_base?: string | null
  deployment_name?: string | null
  is_primary: boolean
  is_fallback: boolean
}

type AgentModelsResponse = {
  models: AgentModelDeployment[]
}

const MULTI_AGENT_MODEL_ROWS = [
  { key: 'technical', label: 'Technical', description: '技术面 Agent，负责 K 线、均线、成交量和趋势形态。' },
  { key: 'intel', label: 'Intel', description: '情报 Agent，负责新闻、公告、基本面和市场信息。' },
  { key: 'risk', label: 'Risk', description: '风险 Agent，负责减持、业绩预警、监管和异常波动。' },
  { key: 'decision', label: 'Decision', description: '决策 Agent，汇总各子 Agent 结论并生成最终建议。' },
]

function normalizeValue(value: unknown): string {
  if (dayjs.isDayjs(value)) return value.format('HH:mm')
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (value === null || value === undefined) return ''
  return String(value)
}

function parseAgentModelMap(value: string): Record<string, string> {
  if (!value.trim()) return {}
  try {
    const parsed = JSON.parse(value) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    const result: Record<string, string> = {}
    for (const row of MULTI_AGENT_MODEL_ROWS) {
      const rawValue = (parsed as Record<string, unknown>)[row.key]
      if (typeof rawValue === 'string' && rawValue.trim()) {
        result[row.key] = rawValue.trim()
      }
    }
    return result
  } catch {
    return {}
  }
}

function serializeAgentModelMap(value: Record<string, string>): string {
  const entries = MULTI_AGENT_MODEL_ROWS
    .map((row) => [row.key, value[row.key]?.trim() ?? ''] as const)
    .filter(([, model]) => model.length > 0)
  return entries.length ? JSON.stringify(Object.fromEntries(entries)) : ''
}

/** 解析逗号分隔的技能字符串为 ID 数组。特殊值 "all" 展开为全选。 */
function parseAgentSkills(value: string): string[] {
  if (!value.trim()) return []
  const ids = value.split(',').map((s) => s.trim()).filter(Boolean)
  if (ids.includes('all')) return ['all']
  return ids
}

/** 将选中的技能 ID 数组序列化为逗号分隔字符串 */
function serializeAgentSkills(selected: string[], allSkillIds: string[]): string {
  if (selected.includes('all') || selected.length === 0) {
    return selected.includes('all') ? 'all' : ''
  }
  const ordered = allSkillIds.filter((id) => selected.includes(id))
  return ordered.join(',')
}

function formatAgentModelOption(model: AgentModelDeployment): string {
  const markers = [
    model.is_primary ? '主模型' : '',
    model.is_fallback ? '备用' : '',
  ].filter(Boolean)
  const markerText = markers.length ? ` · ${markers.join('/')}` : ''
  return `${model.model}${markerText}`
}

function uniqueModelOptions(models: AgentModelDeployment[]) {
  const seen = new Set<string>()
  return models
    .map((model) => ({
      value: model.model,
      label: formatAgentModelOption(model),
    }))
    .filter((option) => {
      if (!option.value || seen.has(option.value)) return false
      seen.add(option.value)
      return true
    })
}

function renderControl(item: ConfigItem) {
  const schema = item.schema
  if (!schema?.is_editable) {
    return <Input disabled />
  }
  if (schema.ui_control === 'switch' || schema.data_type === 'boolean') {
    return <Switch />
  }
  if (schema.ui_control === 'number' || schema.data_type === 'integer' || schema.data_type === 'number') {
    return <InputNumber className="admin-setting-number" />
  }
  if (schema.ui_control === 'time' || schema.data_type === 'time') {
    return <TimePicker format="HH:mm" minuteStep={5} style={{ width: 200 }} />
  }
  if (schema.ui_control === 'select' && schema.options?.length) {
    return (
      <Select
        options={schema.options.map((option) => (
          typeof option === 'string'
            ? { label: option, value: option }
            : { label: option.label, value: option.value }
        ))}
      />
    )
  }
  if (schema.ui_control === 'password' || schema.is_sensitive) {
    return <Input.Password autoComplete="new-password" />
  }
  if (schema.ui_control === 'textarea' || schema.data_type === 'array' || schema.data_type === 'json') {
    return <Input.TextArea autoSize={{ minRows: 2, maxRows: 8 }} />
  }
  return <Input />
}

export function SystemSettingsPage() {
  const [form] = Form.useForm<Record<string, unknown>>()
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [agentModels, setAgentModels] = useState<AgentModelDeployment[]>([])
  const [agentModelsLoading, setAgentModelsLoading] = useState(false)
  const [agentModelsError, setAgentModelsError] = useState<string | null>(null)
  const agentModelMapValue = normalizeValue(Form.useWatch('AGENT_MODEL_MAP', form))
  const agentPrimaryModel = normalizeValue(Form.useWatch('AGENT_LITELLM_MODEL', form))
  const primaryModel = normalizeValue(Form.useWatch('LITELLM_MODEL', form))
  const [skills, setSkills] = useState<Array<{ id: string; name: string; description: string }>>([])
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillsError, setSkillsError] = useState<string | null>(null)
  const [defaultSkillId, setDefaultSkillId] = useState<string>('')
  const agentSkillsValue = normalizeValue(Form.useWatch('AGENT_SKILLS', form))

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await requestJson<ConfigResponse>('/api/v1/system/config?include_schema=true')
      setConfig(payload)
      form.setFieldsValue(Object.fromEntries(payload.items.map((item) => {
        const schema = item.schema
        if (schema?.ui_control === 'switch' || schema?.data_type === 'boolean') {
          return [item.key, item.value === 'true' || item.value === '1']
        }
        if (schema?.data_type === 'integer' || schema?.data_type === 'number') {
          return [item.key, item.value === '' ? undefined : Number(item.value)]
        }
        if (schema?.ui_control === 'time' || schema?.data_type === 'time') {
          const parsed = dayjs(item.value, 'HH:mm')
          return [item.key, parsed.isValid() ? parsed : undefined]
        }
        return [item.key, item.value]
      })))
    } catch (err) {
      setError(err instanceof Error ? err.message : '配置加载失败')
    } finally {
      setLoading(false)
    }
  }, [form])

  useEffect(() => {
    const task = window.setTimeout(() => {
      void load()
    }, 0)
    return () => window.clearTimeout(task)
  }, [load])

  const agentModelMapItem = useMemo(
    () => config?.items.find((item) => item.key === 'AGENT_MODEL_MAP'),
    [config],
  )

  const agentSkillsItem = useMemo(
    () => config?.items.find((item) => item.key === 'AGENT_SKILLS'),
    [config],
  )

  useEffect(() => {
    if (!agentSkillsItem) return
    let cancelled = false
    const task = window.setTimeout(() => {
      setSkillsLoading(true)
      setSkillsError(null)
      void requestJson<{ skills: Array<{ id: string; name: string; description: string }>; default_skill_id: string }>('/api/v1/agent/skills')
        .then((payload) => {
          if (!cancelled) {
            setSkills(payload.skills ?? [])
            setDefaultSkillId(payload.default_skill_id ?? '')
          }
        })
        .catch((err) => {
          if (!cancelled) setSkillsError(err instanceof Error ? err.message : '策略列表加载失败')
        })
        .finally(() => {
          if (!cancelled) setSkillsLoading(false)
        })
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(task)
    }
  }, [agentSkillsItem])

  useEffect(() => {
    if (!agentModelMapItem) return
    let cancelled = false
    const task = window.setTimeout(() => {
      setAgentModelsLoading(true)
      setAgentModelsError(null)
      void requestJson<AgentModelsResponse>('/api/v1/agent/models')
        .then((payload) => {
          if (!cancelled) setAgentModels(payload.models ?? [])
        })
        .catch((err) => {
          if (!cancelled) setAgentModelsError(err instanceof Error ? err.message : '模型列表加载失败')
        })
        .finally(() => {
          if (!cancelled) setAgentModelsLoading(false)
        })
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(task)
    }
  }, [agentModelMapItem])

  const groupedItems = useMemo(() => {
    const groups = new Map<string, ConfigItem[]>()
    for (const item of config?.items ?? []) {
      const category = item.schema?.category || 'uncategorized'
      const items = groups.get(category) ?? []
      items.push(item)
      groups.set(category, items)
    }
    return Array.from(groups.entries())
      .map(([category, items]) => ({
        key: category,
        label: getCategoryTitle(category),
        items: items.sort((a, b) => (a.schema?.display_order ?? 9999) - (b.schema?.display_order ?? 9999)),
      }))
      .sort((a, b) => (a.items[0]?.schema?.display_order ?? 9999) - (b.items[0]?.schema?.display_order ?? 9999))
  }, [config])

  const agentModelOptions = useMemo(() => {
    const options = uniqueModelOptions(agentModels)
    const modelMap = parseAgentModelMap(agentModelMapValue)
    for (const assignedModel of Object.values(modelMap)) {
      if (assignedModel && !options.some((option) => option.value === assignedModel)) {
        options.push({
          value: assignedModel,
          label: `${assignedModel}（当前值，模型列表未返回）`,
        })
      }
    }
    return options
  }, [agentModelMapValue, agentModels])

  const updateAgentModel = (agentKey: string, model: string) => {
    const next = { ...parseAgentModelMap(agentModelMapValue) }
    if (model) {
      next[agentKey] = model
    } else {
      delete next[agentKey]
    }
    form.setFieldValue('AGENT_MODEL_MAP', serializeAgentModelMap(next))
  }

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    try {
      const values = form.getFieldsValue(true)
      const items = config.items
        .filter((item) => item.schema?.is_editable !== false)
        .map((item) => ({
          key: item.key,
          value: normalizeValue(values[item.key]),
        }))
        .filter((item) => item.value !== normalizeValue(config.items.find((current) => current.key === item.key)?.value))

      if (!items.length) {
        message.info('没有需要保存的改动')
        return
      }

      const payload = await requestJson<UpdateResponse>('/api/v1/system/config', {
        method: 'PUT',
        body: JSON.stringify({
          config_version: config.config_version,
          mask_token: config.mask_token,
          reload_now: true,
          items,
        }),
      })
      message.success(`已保存 ${payload.updated_keys.length} 项配置`)
      if (payload.warnings?.length) {
        message.warning(payload.warnings[0])
      }
      await load()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <Spin />
  }

  if (error) {
    return <Alert type="error" showIcon message="系统设置加载失败" description={error} />
  }

  return (
    <div className="admin-settings-page">
      <div className="table-title">
        <div>
          <Title level={5}>
            系统设置
            <Tooltip title="管理平台级配置，修改后点击保存即可生效。敏感字段（如 API Key）保存后不会回显原始值。">
              <QuestionCircleOutlined style={{ marginLeft: 8, color: '#8c8c8c', fontSize: 16, cursor: 'help' }} />
            </Tooltip>
          </Title>
          <Text type="secondary">管理平台级配置，保存后写入全局配置。</Text>
        </div>
        <Space>
          <Button onClick={() => void load()} disabled={saving}>刷新</Button>
          <Button type="primary" onClick={() => void handleSave()} loading={saving}>保存</Button>
        </Space>
      </div>

      <Form form={form} layout="vertical" className="admin-settings-form">
        {agentModelMapItem ? (
          <Form.Item name="AGENT_MODEL_MAP" hidden>
            <Input />
          </Form.Item>
        ) : null}
        <Tabs
          items={groupedItems.map((group) => ({
            key: group.key,
            label: group.label,
            children: (
              <Card>
                {group.key === 'agent' && agentModelMapItem ? (
                  <div
                    style={{
                      marginBottom: 16,
                      padding: 16,
                      border: '1px solid #f0f0f0',
                      borderRadius: 8,
                    }}
                  >
                    <Title level={5} style={{ marginTop: 0 }}>平台默认 Agent 模型分配</Title>
                    <Text type="secondary">
                      未获得 C 端 Agent 模型分配权限的用户会继承这里的默认配置；留空则继承 Agent 主模型。
                    </Text>
                    <div style={{ marginTop: 16, marginBottom: 12 }}>
                      <Text type="secondary">
                        当前继承目标：
                      </Text>
                      <Text code>{agentPrimaryModel || primaryModel || '平台默认 Agent 主模型'}</Text>
                    </div>
                    {agentModelsError ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="模型列表加载失败"
                        description={agentModelsError}
                        style={{ marginBottom: 12 }}
                      />
                    ) : null}
                    {!agentModelsError && !agentModelsLoading && agentModelOptions.length === 0 ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="暂无可选模型"
                        description="请先在平台 AI 模型配置中添加并启用模型渠道。"
                        style={{ marginBottom: 12 }}
                      />
                    ) : null}
                    <Space direction="vertical" size={12} style={{ width: '100%' }}>
                      {MULTI_AGENT_MODEL_ROWS.map((agent) => {
                        const modelMap = parseAgentModelMap(agentModelMapValue)
                        return (
                          <div
                            key={agent.key}
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'minmax(0, 1fr) minmax(240px, 360px)',
                              gap: 16,
                              alignItems: 'center',
                              padding: 12,
                              border: '1px solid #f0f0f0',
                              borderRadius: 8,
                            }}
                          >
                            <div>
                              <Text strong>{agent.label}</Text>
                              <div>
                                <Text type="secondary">{agent.description}</Text>
                              </div>
                            </div>
                            <Select
                              allowClear
                              showSearch
                              placeholder="继承 Agent 主模型"
                              value={modelMap[agent.key] || undefined}
                              loading={agentModelsLoading}
                              disabled={saving || agentModelsLoading || agentModelOptions.length === 0}
                              options={agentModelOptions}
                              optionFilterProp="label"
                              onChange={(value) => updateAgentModel(agent.key, value || '')}
                            />
                          </div>
                        )
                      })}
                    </Space>
                  </div>
                ) : null}
                {group.key === 'agent' && agentSkillsItem ? (
                  <div
                    style={{
                      marginBottom: 16,
                      padding: 16,
                      border: '1px solid #f0f0f0',
                      borderRadius: 8,
                    }}
                  >
                    <Title level={5} style={{ marginTop: 0 }}>平台默认 Agent 策略技能</Title>
                    <Text type="secondary">
                      选择希望在分析时激活的策略技能。勾选"all（全部策略）"可一键启用全部，留空则使用默认主策略。
                    </Text>
                    <div style={{ marginTop: 16, marginBottom: 12 }}>
                      <Text type="secondary">
                        默认策略：
                      </Text>
                      <Text code>{defaultSkillId || 'bull_trend'}</Text>
                    </div>
                    {skillsError ? (
                      <Alert
                        type="warning"
                        showIcon
                        message="策略列表加载失败"
                        description={skillsError}
                        style={{ marginBottom: 12 }}
                      />
                    ) : null}
                    <Select
                      mode="multiple"
                      allowClear
                      showSearch
                      placeholder="选择 Agent 策略技能"
                      style={{ width: '100%' }}
                      value={
                        (() => {
                          const selected = parseAgentSkills(agentSkillsValue)
                          if (selected.includes('all')) return ['all']
                          return selected
                        })()
                      }
                      loading={skillsLoading}
                      disabled={saving || skillsLoading}
                      options={[
                        { label: 'all（全部策略）', value: 'all' },
                        ...skills.map((s) => ({
                          label: `${s.id} — ${s.name}`,
                          value: s.id,
                        })),
                      ]}
                      optionFilterProp="label"
                      onChange={(values: string[]) => {
                        const allIds = skills.map((s) => s.id)
                        form.setFieldValue('AGENT_SKILLS', serializeAgentSkills(values, allIds))
                      }}
                    />
                  </div>
                ) : null}
                {group.items.filter((item) => item.key !== 'AGENT_MODEL_MAP' && item.key !== 'AGENT_SKILLS').map((item) => {
                  const accessLevelTag = item.schema?.access_level === 'user' ? (
                    <Tag color="blue" style={{ marginLeft: 8, fontSize: 11, lineHeight: '18px' }}>用户可覆盖</Tag>
                  ) : (
                    <Tag style={{ marginLeft: 8, fontSize: 11, lineHeight: '18px' }}>平台设置</Tag>
                  )
                  const labelNode = (
                    <span>
                      {getFieldTitle(item.key, item.schema?.title)}
                      {accessLevelTag}
                      {item.schema?.description ? (
                        <Tooltip title={item.schema.description}>
                          <QuestionCircleOutlined style={{ marginLeft: 6, color: '#8c8c8c', fontSize: 14, cursor: 'help' }} />
                        </Tooltip>
                      ) : null}
                    </span>
                  )
                  return (
                    <Form.Item
                      key={item.key}
                      name={item.key}
                      label={labelNode}
                      valuePropName={item.schema?.ui_control === 'switch' || item.schema?.data_type === 'boolean' ? 'checked' : 'value'}
                    >
                      {renderControl(item)}
                    </Form.Item>
                  )
                })}
              </Card>
            ),
          }))}
        />
      </Form>
    </div>
  )
}
