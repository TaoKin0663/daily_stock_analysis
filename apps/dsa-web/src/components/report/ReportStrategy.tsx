import type React from 'react';
import type { ReportLanguage, ReportStrategy as ReportStrategyType } from '../../types/analysis';
import { Card } from '@heroui/react/card';
import { DashboardPanelHeader } from '../dashboard';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportStrategyProps {
  strategy?: ReportStrategyType;
  language?: ReportLanguage;
}

interface StrategyItemProps {
  label: string;
  value?: string;
  tone: string;
}

const StrategyItem: React.FC<StrategyItemProps> = ({
  label,
  value,
  tone,
}) => (
  <div className="relative rounded-xl border border-default-200 bg-default-50 p-4">
    <div className="flex flex-col">
      <span className="mb-0.5 text-xs text-default-500">{label}</span>
      <span className="text-lg font-bold font-mono text-foreground" style={!value ? { opacity: 0.4 } : undefined}>
        {value || '—'}
      </span>
    </div>
    <div
      className="absolute bottom-0 left-0 right-0 h-0.5 rounded-b-xl"
      style={{ background: `linear-gradient(90deg, transparent, var(${tone}), transparent)` }}
    />
  </div>
);

/**
 * 策略点位区组件 - 终端风格
 */
export const ReportStrategy: React.FC<ReportStrategyProps> = ({ strategy, language = 'zh' }) => {
  if (!strategy) {
    return null;
  }

  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);

  const strategyItems = [
    {
      label: text.idealBuy,
      value: strategy.idealBuy,
      tone: '--home-strategy-buy',
    },
    {
      label: text.secondaryBuy,
      value: strategy.secondaryBuy,
      tone: '--home-strategy-secondary',
    },
    {
      label: text.stopLoss,
      value: strategy.stopLoss,
      tone: '--home-strategy-stop',
    },
    {
      label: text.takeProfit,
      value: strategy.takeProfit,
      tone: '--home-strategy-take',
    },
  ];

  return (
    <Card>
      <Card.Header className="pb-0">
        <DashboardPanelHeader
          eyebrow={text.strategyPoints}
          title={text.sniperLevels}
        />
      </Card.Header>
      <Card.Content className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {strategyItems.map((item) => (
            <StrategyItem key={item.label} {...item} />
          ))}
        </div>
      </Card.Content>
    </Card>
  );
};
