import type React from 'react';
import { Percent } from 'lucide-react';
import { Card } from '@heroui/react/card';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  FinancialReport,
  ProfitabilityAnalysisReport,
  ProfitabilityRow,
  ReportLanguage,
} from '../../types/analysis';
import { normalizeReportLanguage } from '../../utils/reportLanguage';

interface FinancialProfitabilitySectionProps {
  financialReport?: FinancialReport;
  profitabilityAnalysis?: ProfitabilityAnalysisReport;
  language?: ReportLanguage;
  compact?: boolean;
}

type ProfitabilityRowPayload = ProfitabilityRow & {
  report_date?: string | null;
  gross_margin?: number | string | null;
  net_margin?: number | string | null;
};

type ProfitabilityChartPoint = {
  period: string;
  grossMargin: number;
  netMargin?: number | null;
  roe?: number | null;
};

const coerceFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === 'string') {
    const parsed = Number(value.trim().replace(/%$/, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const hasFiniteMetric = (value?: number | null): boolean =>
  typeof value === 'number' && Number.isFinite(value);

const normalizeRow = (row: ProfitabilityRowPayload): ProfitabilityRow => ({
  period: row.period || row.reportDate || row.report_date || undefined,
  reportDate: row.reportDate || row.report_date || null,
  grossMargin: coerceFiniteNumber(row.grossMargin ?? row.gross_margin),
  netMargin: coerceFiniteNumber(row.netMargin ?? row.net_margin),
  roe: coerceFiniteNumber(row.roe),
});

const getProfitabilityRows = (financialReport?: FinancialReport): ProfitabilityRow[] => {
  const rows = financialReport?.profitability?.rows;
  const normalizedRows = Array.isArray(rows)
    ? rows.map((row) => normalizeRow(row as ProfitabilityRowPayload))
    : [];

  const validRows = normalizedRows.filter((row) => (
    Boolean(row.period || row.reportDate)
    && (
      hasFiniteMetric(row.grossMargin)
      || hasFiniteMetric(row.netMargin)
      || hasFiniteMetric(row.roe)
    )
  ));

  if (validRows.length > 0) {
    return validRows;
  }

  const fallbackRow: ProfitabilityRow = {
    period: financialReport?.reportDate || 'latest',
    reportDate: financialReport?.reportDate || null,
    grossMargin: coerceFiniteNumber(financialReport?.grossMargin),
    netMargin: coerceFiniteNumber(financialReport?.netMargin),
    roe: coerceFiniteNumber(financialReport?.roe),
  };

  return hasFiniteMetric(fallbackRow.grossMargin)
    || hasFiniteMetric(fallbackRow.netMargin)
    || hasFiniteMetric(fallbackRow.roe)
    ? [fallbackRow]
    : [];
};

const formatPercent = (value?: number | null): string => {
  if (!hasFiniteMetric(value)) {
    return '--';
  }
  return `${Number(value).toFixed(2)}%`;
};

const getPeriodLabel = (row: ProfitabilityRow): string =>
  String(row.period || row.reportDate || '--').replace(/ 00:00:00$/, '');

const cleanText = (value?: string | null): string => (value || '').trim();

const getAnalysisItems = (analysis?: ProfitabilityAnalysisReport) => {
  const items = Array.isArray(analysis?.items) ? analysis.items : [];
  return items
    .map((item) => ({
      title: cleanText(item?.title),
      content: cleanText(item?.content),
    }))
    .filter((item) => item.title || item.content);
};

const toChartData = (rows: ProfitabilityRow[]): ProfitabilityChartPoint[] => rows
  .filter((row) => hasFiniteMetric(row.grossMargin))
  .slice()
  .sort((left, right) => getPeriodLabel(left).localeCompare(getPeriodLabel(right)))
  .map((row) => ({
    period: getPeriodLabel(row),
    grossMargin: Number(row.grossMargin),
    netMargin: row.netMargin,
    roe: row.roe,
  }));

const buildFallbackSummary = (
  rows: ProfitabilityRow[],
  reportLanguage: ReportLanguage,
): string => {
  const latest = rows[0];
  if (!latest) {
    return '';
  }

  const period = getPeriodLabel(latest);
  const metrics = [
    hasFiniteMetric(latest.grossMargin)
      ? `${reportLanguage === 'en' ? 'gross margin' : '毛利率'} ${formatPercent(latest.grossMargin)}`
      : '',
    hasFiniteMetric(latest.netMargin)
      ? `${reportLanguage === 'en' ? 'net margin' : '净利率'} ${formatPercent(latest.netMargin)}`
      : '',
    hasFiniteMetric(latest.roe)
      ? `ROE ${formatPercent(latest.roe)}`
      : '',
  ].filter(Boolean);

  if (metrics.length === 0) {
    return '';
  }

  return reportLanguage === 'en'
    ? `Latest profitability metrics for ${period}: ${metrics.join(', ')}.`
    : `${period} 盈利能力指标：${metrics.join('，')}。`;
};

export const FinancialProfitabilitySection: React.FC<FinancialProfitabilitySectionProps> = ({
  financialReport,
  profitabilityAnalysis,
  language,
  compact = false,
}) => {
  const reportLanguage = normalizeReportLanguage(language);
  const rows = getProfitabilityRows(financialReport);
  const fallbackSummary = buildFallbackSummary(rows, reportLanguage);
  const analysisSummary = cleanText(profitabilityAnalysis?.summary) || fallbackSummary;
  const analysisItems = getAnalysisItems(profitabilityAnalysis);
  const chartData = toChartData(rows);

  if (!analysisSummary && analysisItems.length === 0 && chartData.length === 0) {
    return null;
  }

  const copy = reportLanguage === 'en'
    ? {
      eyebrow: 'FINANCIAL DATA',
      title: 'Profitability',
      grossMargin: 'Gross Margin',
      netMargin: 'Net Margin',
      roe: 'ROE',
      source: 'Source',
      chartTitle: 'Profitability Trend (Gross Margin)',
      chartLabel: 'Profitability trend gross margin chart',
      period: 'Period',
    }
    : {
      eyebrow: '财务数据分析',
      title: '盈利能力',
      grossMargin: '毛利率',
      netMargin: '净利率',
      roe: 'ROE',
      source: '数据源',
      chartTitle: '盈利能力趋势（毛利率）',
      chartLabel: '盈利能力趋势毛利率图表',
      period: '报告期',
    };

  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Percent className="h-4 w-4 text-default-500" aria-hidden="true" />
          <div>
            {!compact ? (
              <div className="text-[11px] font-medium uppercase tracking-wider text-default-500">
                {copy.eyebrow}
              </div>
            ) : null}
            <h3 className="text-base font-semibold text-foreground">{copy.title}</h3>
          </div>
        </div>
        {financialReport?.profitability?.source ? (
          <span className="rounded-md bg-default-100 px-2 py-1 text-[11px] text-default-500">
            {copy.source}: {financialReport.profitability.source}
          </span>
        ) : null}
      </div>

      {analysisSummary || analysisItems.length > 0 ? (
        <div className="space-y-3 text-sm leading-7 text-foreground">
          {analysisSummary ? (
            <p className="whitespace-pre-wrap">{analysisSummary}</p>
          ) : null}
          {analysisItems.length > 0 ? (
            <ul className="space-y-2">
              {analysisItems.map((item, index) => (
                <li key={`${item.title}-${index}`} className="flex gap-2">
                  <span className="mt-[0.72em] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-default-400" />
                  <span>
                    {item.title ? <strong>{item.title}：</strong> : null}
                    {item.content}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {chartData.length > 0 ? (
        <div
          className="min-w-0 rounded-lg border border-subtle bg-background/35 print:break-inside-avoid"
          aria-label={copy.chartLabel}
        >
          <div className="border-b border-subtle px-3 py-2 text-xs font-medium text-default-600">
            {copy.chartTitle}
          </div>
          <div className="h-56 px-2 py-3">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="profitabilityGrossMargin" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--home-action-report-text)" stopOpacity={0.26} />
                    <stop offset="95%" stopColor="var(--home-action-report-text)" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="period"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                  tickFormatter={(value) => formatPercent(Number(value))}
                  width={56}
                />
                <RechartsTooltip
                  cursor={{ stroke: 'var(--home-action-report-text)', strokeOpacity: 0.35 }}
                  formatter={(value, name, item) => {
                    if (name === 'grossMargin') {
                      const payload = item.payload as ProfitabilityChartPoint;
                      return [
                        `${formatPercent(Number(value))} / ${copy.netMargin} ${formatPercent(payload.netMargin)} / ${copy.roe} ${formatPercent(payload.roe)}`,
                        copy.grossMargin,
                      ];
                    }
                    return [String(value), String(name)];
                  }}
                  labelFormatter={(label) => `${copy.period}: ${label}`}
                  contentStyle={{
                    background: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: 8,
                    color: 'hsl(var(--foreground))',
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Area
                  type="monotone"
                  dataKey="grossMargin"
                  stroke="var(--home-action-report-text)"
                  strokeWidth={2}
                  fill="url(#profitabilityGrossMargin)"
                  name="grossMargin"
                  dot={{ r: 3, strokeWidth: 2 }}
                  activeDot={{ r: 4 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
    </>
  );

  if (compact) {
    return <div className="space-y-3">{content}</div>;
  }

  return (
    <Card className="text-left">
      <Card.Content className="space-y-3">
        {content}
      </Card.Content>
    </Card>
  );
};
