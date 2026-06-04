import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { agentApi, type SkillInfo } from '../../api/agent';
import { getParsedApiError, type ParsedApiError } from '../../api/error';
import { ApiErrorAlert, InlineAlert } from '../common';
import { SettingsSectionCard } from './SettingsSectionCard';
import type { SystemConfigItem } from '../../types/systemConfig';

/** 已知技能的硬编码回退列表（API 不可用时使用） */
const FALLBACK_SKILLS: SkillInfo[] = [
  { id: 'bull_trend', name: '主升浪趋势', description: '放量上涨 + 均线多头排列' },
  { id: 'ma_golden_cross', name: '均线金叉', description: '短期均线上穿长期均线' },
  { id: 'volume_breakout', name: '放量突破', description: '价格突破近期高点 + 成交量放大' },
  { id: 'shrink_pullback', name: '缩量回踩', description: '回踩均线 + 量能萎缩，低吸点' },
  { id: 'bottom_volume', name: '底部放量', description: '地量见地价，底部反转信号' },
  { id: 'dragon_head', name: '龙头策略', description: '强势龙头，趋势延续追涨' },
  { id: 'one_yang_three_yin', name: '一阳夹三阴', description: '主力洗盘后强势反包形态' },
  { id: 'box_oscillation', name: '箱体震荡', description: '区间高抛低吸' },
  { id: 'chan_theory', name: '缠论', description: '缠中说禅理论：笔/线段/中枢' },
  { id: 'emotion_cycle', name: '情绪周期', description: '市场情绪高低点轮动' },
  { id: 'wave_theory', name: '波浪理论', description: '艾略特波浪计数' },
];

interface AgentSkillsEditorProps {
  item: SystemConfigItem;
  disabled: boolean;
  onChange: (key: string, value: string) => void;
}

/**
 * 解析逗号分隔的技能 ID 字符串为 Set。
 * 特殊值 "all" 表示全选，返回包含 "all" 的 Set。
 */
function parseSelectedSkills(rawValue: string): Set<string> {
  if (!rawValue.trim()) {
    return new Set();
  }
  const ids = rawValue
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  if (ids.includes('all')) {
    return new Set(['all']);
  }
  return new Set(ids);
}

/**
 * 将选中的技能 ID Set 序列化为逗号分隔字符串。
 * 选中 "all" 时直接返回 "all"。
 */
function serializeSelectedSkills(selected: Set<string>, allSkillIds: string[]): string {
  if (selected.has('all')) {
    return 'all';
  }
  // 保持原始 skills 列表的顺序
  const ordered = allSkillIds.filter((id) => selected.has(id));
  return ordered.join(',');
}

export const AgentSkillsEditor: React.FC<AgentSkillsEditorProps> = ({
  item,
  disabled,
  onChange,
}) => {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<ParsedApiError | null>(null);
  const [defaultSkillId, setDefaultSkillId] = useState<string>('');

  const rawValue = String(item.value ?? '');
  const selectedSkills = useMemo(() => parseSelectedSkills(rawValue), [rawValue]);
  const allSkillIds = useMemo(() => skills.map((s) => s.id), [skills]);
  const isAllSelected = selectedSkills.has('all');

  // 加载可用技能列表
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);

    void agentApi
      .getSkills()
      .then((payload) => {
        if (!cancelled) {
          setSkills(payload.skills || []);
          setDefaultSkillId(payload.default_skill_id || '');
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(getParsedApiError(error));
          // API 失败时使用硬编码回退列表
          setSkills(FALLBACK_SKILLS);
          setDefaultSkillId('bull_trend');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSkill = (skillId: string) => {
    const next = new Set(selectedSkills);

    if (skillId === 'all') {
      // 切换 "all"：如果已全选则清空，否则设为 all
      if (next.has('all')) {
        next.clear();
      } else {
        next.clear();
        next.add('all');
      }
    } else {
      // 如果当前是 "all" 模式，先清空
      if (next.has('all')) {
        next.clear();
      }
      // 切换具体技能
      if (next.has(skillId)) {
        next.delete(skillId);
      } else {
        next.add(skillId);
      }
    }

    onChange(item.key, serializeSelectedSkills(next, allSkillIds));
  };

  const defaultSkillName = defaultSkillId
    ? (skills.find((s) => s.id === defaultSkillId)?.name ?? defaultSkillId)
    : '';
  const inheritedHint = defaultSkillName
    ? `留空时默认使用：${defaultSkillName}`
    : '留空时使用系统内置默认策略';

  return (
    <SettingsSectionCard
      title="Agent 策略技能"
      description={`选择希望在分析时激活的策略技能。勾选 all 可一键启用全部策略。${inheritedHint}。`}
    >
      <div className="space-y-4">
        {/* 加载/错误状态 */}
        {isLoading ? (
          <p className="text-xs text-muted-text">正在加载可用策略...</p>
        ) : null}
        {loadError ? (
          <ApiErrorAlert error={loadError} />
        ) : null}
        {!isLoading && !loadError && skills.length === 0 ? (
          <InlineAlert
            variant="warning"
            title="暂无可选策略"
            message="未能获取策略技能列表，请检查 Agent 策略目录配置。"
          />
        ) : null}

        {/* "全部" 快捷开关 */}
        {skills.length > 0 ? (
          <label
            className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
              disabled ? 'pointer-events-none opacity-50' : ''
            } ${
              isAllSelected
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border settings-border bg-background/40 text-muted-text hover:border-primary/30 hover:text-foreground'
            }`}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={isAllSelected}
              disabled={disabled}
              onChange={() => toggleSkill('all')}
            />
            {isAllSelected ? '✓ 全部策略（已启用）' : '全部策略（all）'}
          </label>
        ) : null}

        {/* 技能标签网格 */}
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => {
            const isSelected = isAllSelected || selectedSkills.has(skill.id);
            return (
              <label
                key={skill.id}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                  disabled || isAllSelected ? 'pointer-events-none opacity-60' : ''
                } ${
                  isSelected
                    ? 'border-primary/40 bg-primary/10 text-primary shadow-sm'
                    : 'border settings-border bg-background/40 text-muted-text hover:border-primary/30 hover:text-foreground hover:shadow-sm'
                }`}
                title={skill.description}
              >
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={isSelected}
                  disabled={disabled || isAllSelected}
                  onChange={() => toggleSkill(skill.id)}
                />
                {skill.name}
              </label>
            );
          })}
        </div>
      </div>
    </SettingsSectionCard>
  );
};
