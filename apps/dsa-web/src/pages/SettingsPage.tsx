import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ListBox, Select } from '@heroui/react';
import { useAuth, useSystemConfig } from '../hooks';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { systemConfigApi } from '../api/systemConfig';
import { agentApi, type AgentModelDeployment } from '../api/agent';
import { ApiErrorAlert, Button, ConfirmDialog, EmptyState, InlineAlert } from '../components/common';
import {
  AgentSkillsEditor,
  AuthSettingsCard,
  ChangePasswordCard,
  LLMChannelEditor,
  SettingsCategoryNav,
  SettingsAlert,
  SettingsField,
  SettingsLoading,
  SettingsSectionCard,
} from '../components/settings';
import { WEB_BUILD_INFO } from '../utils/constants';
import { getCategoryDescriptionZh } from '../utils/systemConfigI18n';
import type { SystemConfigCategory, SystemConfigItem } from '../types/systemConfig';

type DesktopWindow = Window & {
  dsaDesktop?: {
    version?: string;
  };
};

function getDesktopAppVersion() {
  if (typeof window === 'undefined') {
    return '';
  }

  return (window as DesktopWindow).dsaDesktop?.version?.trim() || '';
}

function formatDesktopEnvFilename() {
  const now = new Date();
  const pad = (value: number) => value.toString().padStart(2, '0');
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `dsa-desktop-env_${date}_${time}.env`;
}

const MULTI_AGENT_MODEL_ROWS = [
  { key: 'technical', label: 'Technical', description: '价格、成交量、趋势及形态信号的技术分析工具' },
  { key: 'intel', label: 'Intel', description: '新闻、公告、基本面及市场背景的情报分析工具' },
  { key: 'risk', label: 'Risk', description: '风险筛查工具，用于预警、监管事件及异常波动' },
  { key: 'decision', label: 'Decision', description: '决策代理用于综合各子代理的意见并输出最终结论。' },
];

function parseAgentModelMap(value: string): Record<string, string> {
  if (!value.trim()) {
    return {};
  }

  try {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {};
    }

    const result: Record<string, string> = {};
    for (const row of MULTI_AGENT_MODEL_ROWS) {
      const rawValue = (parsed as Record<string, unknown>)[row.key];
      if (typeof rawValue === 'string' && rawValue.trim()) {
        result[row.key] = rawValue.trim();
      }
    }
    return result;
  } catch {
    return {};
  }
}

function serializeAgentModelMap(value: Record<string, string>): string {
  const entries = MULTI_AGENT_MODEL_ROWS
    .map((row) => [row.key, value[row.key]?.trim() ?? ''] as const)
    .filter(([, model]) => model.length > 0);
  return entries.length ? JSON.stringify(Object.fromEntries(entries)) : '';
}

function formatAgentModelOption(model: AgentModelDeployment): string {
  const markers = [
    model.is_primary ? 'primary' : '',
    model.is_fallback ? 'fallback' : '',
  ].filter(Boolean);
  const markerText = markers.length ? ` - ${markers.join('/')}` : '';
  return `${model.model}${markerText}`;
}

function uniqueModelOptions(models: AgentModelDeployment[]) {
  const seen = new Set<string>();
  return models
    .map((model) => ({
      value: model.model,
      label: formatAgentModelOption(model),
    }))
    .filter((option) => {
      if (!option.value || seen.has(option.value)) {
        return false;
      }
      seen.add(option.value);
      return true;
    });
}

interface AgentModelAssignmentCardProps {
  item: SystemConfigItem;
  agentPrimaryModel: string;
  primaryModel: string;
  disabled: boolean;
  onChange: (key: string, value: string) => void;
}

const AgentModelAssignmentCard: React.FC<AgentModelAssignmentCardProps> = ({
  item,
  agentPrimaryModel,
  primaryModel,
  disabled,
  onChange,
}) => {
  const [models, setModels] = useState<AgentModelDeployment[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelLoadError, setModelLoadError] = useState<ParsedApiError | null>(null);
  const modelMap = useMemo(() => parseAgentModelMap(String(item.value ?? '')), [item.value]);
  const modelOptions = useMemo(() => {
    const options = uniqueModelOptions(models);
    for (const assignedModel of Object.values(modelMap)) {
      if (assignedModel && !options.some((option) => option.value === assignedModel)) {
        options.push({
          value: assignedModel,
          label: `${assignedModel}（当前值，平台模型列表未返回）`,
        });
      }
    }
    return options;
  }, [modelMap, models]);
  const inheritedModel = agentPrimaryModel || primaryModel || '平台默认 Agent 主模型';

  useEffect(() => {
    let cancelled = false;
    setIsLoadingModels(true);
    setModelLoadError(null);

    void agentApi.getModels()
      .then((payload) => {
        if (!cancelled) {
          setModels(payload.models || []);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setModelLoadError(getParsedApiError(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingModels(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const updateAgentModel = (agentKey: string, model: string) => {
    const next = { ...modelMap };
    if (model) {
      next[agentKey] = model;
    } else {
      delete next[agentKey];
    }
    onChange(item.key, serializeAgentModelMap(next));
  };

  return (
    <SettingsSectionCard
      title="Agent 模型分配"
      description="多 Agent 模式下可为每个子 Agent 指定平台已配置模型；留空则继承 Agent 主模型。"
    >
      <div className="space-y-4">
        <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3 text-xs leading-6 text-muted-text">
          当前继承目标：<span className="font-mono text-foreground">{inheritedModel}</span>
        </div>
        {modelLoadError ? (
          <ApiErrorAlert error={modelLoadError} />
        ) : null}
        {!modelLoadError && !isLoadingModels && modelOptions.length === 0 ? (
          <InlineAlert
            variant="warning"
            title="暂无可选模型"
            message="请先让平台管理员添加并启用模型渠道。"
          />
        ) : null}
        <div className="space-y-3">
          {MULTI_AGENT_MODEL_ROWS.map((agent) => (
            <div
              key={agent.key}
              className="grid gap-2 rounded-2xl border settings-border bg-background/30 px-4 py-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,320px)] md:items-center"
            >
              <div className="min-w-0">
                <div className="text-sm font-semibold text-foreground">{agent.label}</div>
                <p className="mt-1 text-xs leading-5 text-muted-text">{agent.description}</p>
              </div>
              <Select
                aria-label={`${agent.label} model`}
                // selectedKey={modelMap[agent.key] ?? null}
                // onSelectionChange={(key) => updateAgentModel(agent.key, key === null ? '' : String(key))}
                value={modelMap[agent.key] ?? null}
                onChange={(key) => updateAgentModel(agent.key, key === null ? '' : String(key))}
                isDisabled={disabled || isLoadingModels || modelOptions.length === 0}
                placeholder="继承 Agent 主模型"
                fullWidth
              >
                <Select.Trigger>
                  <Select.Value />
                  <Select.Indicator />
                </Select.Trigger>
                <Select.Popover>
                  <ListBox>
                    {modelOptions.map((option) => (
                      <ListBox.Item key={option.value} id={option.value} textValue={option.label}>
                        {option.label}
                        <ListBox.ItemIndicator />
                      </ListBox.Item>
                    ))}
                  </ListBox>
                </Select.Popover>
              </Select>
            </div>
          ))}
        </div>
        {isLoadingModels ? (
          <p className="text-xs text-muted-text">正在加载平台模型...</p>
        ) : null}
      </div>
    </SettingsSectionCard>
  );
};

const SettingsPage: React.FC = () => {
  const { passwordChangeable, currentUser } = useAuth();
  const isAdmin = currentUser?.isAdmin ?? false;
  const [desktopActionError, setDesktopActionError] = useState<ParsedApiError | null>(null);
  const [desktopActionSuccess, setDesktopActionSuccess] = useState<string>('');
  const [isExportingEnv, setIsExportingEnv] = useState(false);
  const [isImportingEnv, setIsImportingEnv] = useState(false);
  const [showImportConfirm, setShowImportConfirm] = useState(false);
  const desktopImportRef = useRef<HTMLInputElement | null>(null);
  const isDesktopRuntime = typeof window !== 'undefined' && Boolean((window as DesktopWindow).dsaDesktop);
  const desktopAppVersion = getDesktopAppVersion();
  const shouldShowDesktopVersionCard = Boolean(desktopAppVersion);

  // Set page title
  useEffect(() => {
    document.title = '系统设置 - DSA';
  }, []);

  const {
    categories,
    itemsByCategory,
    issueByKey,
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount,
    toast,
    clearToast,
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,
    load,
    retry,
    save,
    resetDraft,
    setDraftValue,
    refreshAfterExternalSave,
    configVersion,
    maskToken,
  } = useSystemConfig();

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 3200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  const rawActiveItems = itemsByCategory[activeCategory] || [];
  const rawActiveItemMap = new Map(rawActiveItems.map((item) => [item.key, String(item.value ?? '')]));
  const aiModelItemMap = new Map((itemsByCategory['ai_model'] || []).map((item) => [item.key, String(item.value ?? '')]));
  const agentArchValue =
    (itemsByCategory['agent'] || []).find((i) => i.key === 'AGENT_ARCH')?.value || 'single';
  const agentModelMapItem = (itemsByCategory['agent'] || []).find((i) => i.key === 'AGENT_MODEL_MAP');
  const agentSkillsItem = (itemsByCategory['agent'] || []).find((i) => i.key === 'AGENT_SKILLS');
  const primaryModelValue = aiModelItemMap.get('LITELLM_MODEL') || '';
  const agentPrimaryModelValue = aiModelItemMap.get('AGENT_LITELLM_MODEL') || '';
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());

  // Hide channel-managed and legacy provider-specific LLM keys from the
  // generic form only when channel config is the active runtime source.
  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const AI_MODEL_HIDDEN_KEYS = new Set([
    'AGENT_MODEL_MAP',
    'LLM_CHANNELS',
    'LLM_TEMPERATURE',
    'LITELLM_MODEL',
    'AGENT_LITELLM_MODEL',
    'LITELLM_FALLBACK_MODELS',
    'AIHUBMIX_KEY',
    'DEEPSEEK_API_KEY',
    'DEEPSEEK_API_KEYS',
    'GEMINI_API_KEY',
    'GEMINI_API_KEYS',
    'GEMINI_MODEL',
    'GEMINI_MODEL_FALLBACK',
    'GEMINI_TEMPERATURE',
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_API_KEYS',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_TEMPERATURE',
    'ANTHROPIC_MAX_TOKENS',
    'OPENAI_API_KEY',
    'OPENAI_API_KEYS',
    'OPENAI_BASE_URL',
    'OPENAI_MODEL',
    'OPENAI_VISION_MODEL',
    'OPENAI_TEMPERATURE',
    'VISION_MODEL',
  ]);
  const AGENT_HIDDEN_KEYS = new Set<string>([
    'AGENT_MODEL_MAP',
    'AGENT_SKILLS',
  ]);
  const activeItems =
    activeCategory === 'ai_model'
      ? rawActiveItems.filter((item) => {
        if (hasConfiguredChannels && LLM_CHANNEL_KEY_RE.test(item.key)) {
          return false;
        }
        if (hasConfiguredChannels && !hasLitellmConfig && AI_MODEL_HIDDEN_KEYS.has(item.key)) {
          return false;
        }
        return true;
      })
      : activeCategory === 'agent'
        ? rawActiveItems.filter((item) => !AGENT_HIDDEN_KEYS.has(item.key))
        : rawActiveItems;
  const desktopActionDisabled = isLoading || isSaving || isExportingEnv || isImportingEnv;

  const downloadDesktopEnv = async () => {
    setDesktopActionError(null);
    setDesktopActionSuccess('');
    setIsExportingEnv(true);
    try {
      const payload = await systemConfigApi.exportDesktopEnv();
      const blob = new Blob([payload.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = formatDesktopEnvFilename();
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setDesktopActionSuccess('已导出当前已保存的 .env 备份。');
    } catch (error: unknown) {
      setDesktopActionError(getParsedApiError(error));
    } finally {
      setIsExportingEnv(false);
    }
  };

  const beginDesktopImport = () => {
    setDesktopActionError(null);
    setDesktopActionSuccess('');
    if (hasDirty) {
      setShowImportConfirm(true);
      return;
    }
    desktopImportRef.current?.click();
  };

  const handleDesktopImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    setShowImportConfirm(false);
    if (!file) {
      return;
    }

    setDesktopActionError(null);
    setDesktopActionSuccess('');
    setIsImportingEnv(true);
    try {
      const content = await file.text();
      await systemConfigApi.importDesktopEnv({
        configVersion,
        content,
        reloadNow: true,
      });
      const reloaded = await load();
      if (!reloaded) {
        setDesktopActionError(createParsedApiError({
          title: '配置已导入但刷新失败',
          message: '备份已导入，但重新加载配置失败，请手动重载页面。',
          rawMessage: 'Desktop env import succeeded but config refresh failed',
          category: 'http_error',
        }));
        return;
      }
      setDesktopActionSuccess('已导入 .env 备份并重新加载配置。');
    } catch (error: unknown) {
      setDesktopActionError(getParsedApiError(error));
    } finally {
      setIsImportingEnv(false);
    }
  };

  return (
    <div className="settings-page min-h-full px-4 pb-6 pt-4 md:px-6">
      <div className="mb-5 rounded-[1.5rem] bg-card/94 px-5 py-5 backdrop-blur-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">系统设置</h1>
            <p className="text-xs leading-6 text-muted-text">
              统一管理模型、数据源、通知、安全认证与导入能力。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="settings-secondary"
              onClick={resetDraft}
              disabled={isLoading || isSaving}
            >
              重置
            </Button>
            <Button
              type="button"
              variant="settings-primary"
              onClick={() => void save()}
              disabled={!hasDirty || isSaving || isLoading}
              isLoading={isSaving}
              loadingText="保存中..."
            >
              {isSaving ? '保存中...' : `保存配置${dirtyCount ? ` (${dirtyCount})` : ''}`}
            </Button>
          </div>
        </div>

        {saveError ? (
          <ApiErrorAlert
            className="mt-3"
            error={saveError}
            actionLabel={retryAction === 'save' ? '重试保存' : undefined}
            onAction={retryAction === 'save' ? () => void retry() : undefined}
          />
        ) : null}
      </div>

      {loadError ? (
        <ApiErrorAlert
          error={loadError}
          actionLabel={retryAction === 'load' ? '重试加载' : '重新加载'}
          onAction={() => void retry()}
          className="mb-4"
        />
      ) : null}

      {isLoading ? (
        <SettingsLoading />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_1fr]">
          <aside className="lg:sticky lg:top-4 lg:self-start">
            <SettingsCategoryNav
              categories={categories}
              itemsByCategory={itemsByCategory}
              activeCategory={activeCategory}
              onSelect={setActiveCategory}
            />
          </aside>

          <section className="space-y-4">
            {activeCategory === 'system' && isAdmin ? <AuthSettingsCard /> : null}
            {activeCategory === 'system' && isAdmin ? (
              <SettingsSectionCard
                title="版本信息"
                description="用于确认当前 WebUI 静态资源是否已经切换到最新构建。"
              >
                <div
                  className={`grid grid-cols-1 gap-3 ${shouldShowDesktopVersionCard ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}
                >
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      WebUI 版本
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.version}
                    </p>
                  </div>
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      构建标识
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.buildId}
                    </p>
                  </div>
                  <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                      构建时间
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-foreground">
                      {WEB_BUILD_INFO.buildTime}
                    </p>
                  </div>
                  {shouldShowDesktopVersionCard ? (
                    <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">
                        桌面端版本
                      </p>
                      <p className="mt-2 break-all font-mono text-sm text-foreground">
                        {desktopAppVersion}
                      </p>
                    </div>
                  ) : null}
                </div>
                <p className="text-xs leading-6 text-muted-text">
                  重新执行前端构建或 Docker 镜像构建后，此处的构建标识和构建时间会更新，可用来确认当前页面资源是否已切换。
                </p>
                {WEB_BUILD_INFO.isFallbackVersion ? (
                  <p className="text-xs leading-6 text-amber-700 dark:text-amber-300">
                    当前 package.json 仍为占位版本 0.0.0，页面已自动回退展示构建标识，避免误判旧资源仍在生效。
                  </p>
                ) : null}
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' && isDesktopRuntime && isAdmin ? (
              <SettingsSectionCard
                title="配置备份"
                description="导出当前已保存的 .env 备份，或从备份文件恢复桌面端配置。导入会覆盖备份中出现的键并立即重载。"
              >
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Button
                      type="button"
                      variant="settings-secondary"
                      onClick={() => void downloadDesktopEnv()}
                      disabled={desktopActionDisabled}
                      isLoading={isExportingEnv}
                      loadingText="导出中..."
                    >
                      导出 .env
                    </Button>
                    <Button
                      type="button"
                      variant="settings-primary"
                      onClick={beginDesktopImport}
                      disabled={desktopActionDisabled}
                      isLoading={isImportingEnv}
                      loadingText="导入中..."
                    >
                      导入 .env
                    </Button>
                    <input
                      ref={desktopImportRef}
                      type="file"
                      accept=".env,.txt"
                      className="hidden"
                      onChange={(event) => {
                        void handleDesktopImportFile(event);
                      }}
                    />
                  </div>
                  <p className="text-xs leading-6 text-muted-text">
                    导出内容仅包含当前已保存配置，不包含页面上尚未保存的本地草稿。
                  </p>
                  {desktopActionError ? (
                    <ApiErrorAlert
                      error={desktopActionError}
                      actionLabel={desktopActionError.status === 409 ? '重新加载' : undefined}
                      onAction={desktopActionError.status === 409 ? () => void load() : undefined}
                    />
                  ) : null}
                  {!desktopActionError && desktopActionSuccess ? (
                    <SettingsAlert title="操作成功" message={desktopActionSuccess} variant="success" />
                  ) : null}
                </div>
              </SettingsSectionCard>
            ) : null}
            {/* {activeCategory === 'base' ? (
              <SettingsSectionCard
                title="智能导入"
                description="从图片、文件或剪贴板中提取股票代码，并合并到自选股列表。"
              >
                <IntelligentImport
                  stockListValue={
                    (activeItems.find((i) => i.key === 'STOCK_LIST')?.value as string) ?? ''
                  }
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onMerged={async () => {
                    await refreshAfterExternalSave(['STOCK_LIST']);
                  }}
                  disabled={isSaving || isLoading}
                />
              </SettingsSectionCard>
            ) : null} */}
            {activeCategory === 'ai_model' && isAdmin ? (
              <SettingsSectionCard
                title="AI 模型接入"
                description="统一管理模型渠道、基础地址、API Key、主模型与备选模型。"
              >
                <LLMChannelEditor
                  items={rawActiveItems}
                  configVersion={configVersion}
                  maskToken={maskToken}
                  agentArch={agentArchValue}
                  onSaved={async (updatedItems) => {
                    await refreshAfterExternalSave(updatedItems.map((item) => item.key));
                  }}
                  disabled={isSaving || isLoading}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' && passwordChangeable && isAdmin ? (
              <ChangePasswordCard />
            ) : null}
            {activeCategory === 'agent' && agentSkillsItem ? (
              <AgentSkillsEditor
                item={agentSkillsItem}
                disabled={isSaving || isLoading}
                onChange={setDraftValue}
              />
            ) : null}
            {activeCategory === 'agent' && agentArchValue === 'multi' && agentModelMapItem ? (
              <AgentModelAssignmentCard
                item={agentModelMapItem}
                primaryModel={primaryModelValue}
                agentPrimaryModel={agentPrimaryModelValue}
                disabled={isSaving || isLoading}
                onChange={setDraftValue}
              />
            ) : null}
            {activeItems.length ? (
              <SettingsSectionCard
                title="当前分类配置项"
                description={getCategoryDescriptionZh(activeCategory as SystemConfigCategory, '') || '使用统一字段卡片维护当前分类的系统配置。'}
              >
                {activeItems.map((item) => (
                  <SettingsField
                    key={item.key}
                    item={item}
                    value={item.value}
                    disabled={isSaving}
                    onChange={setDraftValue}
                    issues={issueByKey[item.key] || []}
                  />
                ))}
              </SettingsSectionCard>
            ) : (
              <EmptyState
                title="当前分类下暂无配置项"
                description="当前分类没有可编辑字段；可切换左侧分类继续查看其它系统配置。"
                className="settings-surface-panel settings-border-strong border-none bg-transparent shadow-none"
              />
            )}
          </section>
        </div>
      )}

      {toast ? (
        <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
          {toast.type === 'success'
            ? <SettingsAlert title="操作成功" message={toast.message} variant="success" />
            : <ApiErrorAlert error={toast.error} />}
        </div>
      ) : null}
      <ConfirmDialog
        isOpen={showImportConfirm}
        title="导入会覆盖当前草稿"
        message="当前页面还有未保存修改。继续导入会丢弃这些本地草稿，并立即用备份文件中的键值更新已保存配置。"
        confirmText="继续导入"
        cancelText="取消"
        onConfirm={() => {
          setShowImportConfirm(false);
          desktopImportRef.current?.click();
        }}
        onCancel={() => {
          setShowImportConfirm(false);
        }}
      />
    </div>
  );
};

export default SettingsPage;
