import type React from 'react';
import { BarChart3 } from 'lucide-react';
import { Card } from '@heroui/react/card';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { FinancialReport, ReportLanguage, RevenueGrowthRow } from '../../types/analysis';
import { normalizeReportLanguage } from '../../utils/reportLanguage';

interface FinancialRevenueGrowthSectionProps {
  financialReport?: FinancialReport;
  language?: ReportLanguage;
  compact?: boolean;
}

type RevenueChartPoint = {
  fiscalYear: string;
  revenueBillion: number;
  revenueYoy?: number | null;
};

const getRevenueRows = (financialReport?: FinancialReport): RevenueGrowthRow[] => {
  const rows = financialReport?.revenueGrowth?.rows;
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.filter((row) => row?.fiscalYear != null && row?.revenue != null);
};

const formatRevenueBillion = (value?: number | null): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) {
    return '--';
  }
  return (value / 100000000).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatGrowthPct = (value?: number | null): string => {
  if (value === undefined || value === null || !Number.isFinite(value)) {
    return '--';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

const getGrowthStyle = (value?: number | null): React.CSSProperties | undefined => {
  if (value === undefined || value === null || !Number.isFinite(value)) {
    return undefined;
  }
  if (value > 0) {
    return { color: 'var(--home-price-up)' };
  }
  if (value < 0) {
    return { color: 'var(--home-price-down)' };
  }
  return undefined;
};

const toChartData = (rows: RevenueGrowthRow[]): RevenueChartPoint[] => rows
  .slice()
  .sort((left, right) => Number(left.fiscalYear) - Number(right.fiscalYear))
  .map((row) => ({
    fiscalYear: String(row.fiscalYear),
    revenueBillion: Number(row.revenue) / 100000000,
    revenueYoy: row.revenueYoy,
  }))
  .filter((row) => Number.isFinite(row.revenueBillion));

export const FinancialRevenueGrowthSection: React.FC<FinancialRevenueGrowthSectionProps> = ({
  financialReport,
  language,
  compact = false,
}) => {
  const reportLanguage = normalizeReportLanguage(language);
  const rows = getRevenueRows(financialReport);
  if (rows.length === 0) {
    return null;
  }

  const chartData = toChartData(rows);
  const copy = reportLanguage === 'en'
    ? {
      eyebrow: 'FINANCIAL DATA',
      title: 'Revenue Growth',
      year: 'Year',
      revenue: 'Revenue (100M CNY)',
      yoy: 'YoY Growth',
      source: 'Source',
      chartLabel: 'Revenue growth data chart',
    }
    : {
      eyebrow: '财务数据分析',
      title: '营收增长',
      year: '年度',
      revenue: '营业收入（亿）',
      yoy: '同比增长率',
      source: '数据源',
      chartLabel: '营收增长数据图表',
    };

  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-default-500" aria-hidden="true" />
          <div>
            {!compact ? (
              <div className="text-[11px] font-medium uppercase tracking-wider text-default-500">
                {copy.eyebrow}
              </div>
            ) : null}
            <h3 className="text-base font-semibold text-foreground">{copy.title}</h3>
          </div>
        </div>
        {financialReport?.revenueGrowth?.source ? (
          <span className="rounded-md bg-default-100 px-2 py-1 text-[11px] text-default-500">
            {copy.source}: {financialReport.revenueGrowth.source}
          </span>
        ) : null}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full table-fixed text-left text-sm">
          <thead>
            <tr className="border-b border-subtle text-[11px] font-medium uppercase tracking-wide text-default-500">
              <th className="w-1/3 px-2 py-2">{copy.year}</th>
              <th className="w-1/3 px-2 py-2 text-right">{copy.revenue}</th>
              <th className="w-1/3 px-2 py-2 text-right">{copy.yoy}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.fiscalYear} className="border-b border-subtle last:border-b-0">
                <td className="px-2 py-2 font-mono text-foreground">{row.fiscalYear}</td>
                <td className="px-2 py-2 text-right font-mono text-foreground">
                  {formatRevenueBillion(row.revenue)}
                </td>
                <td className="px-2 py-2 text-right font-mono font-semibold" style={getGrowthStyle(row.revenueYoy)}>
                  {formatGrowthPct(row.revenueYoy)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {chartData.length > 0 ? (
        <div
          className="h-56 min-w-0 rounded-lg border border-subtle bg-background/35 px-2 py-3 print:break-inside-avoid"
          aria-label={copy.chartLabel}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="fiscalYear"
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                tickFormatter={(value) => formatRevenueBillion(Number(value) * 100000000)}
                width={56}
              />
              <RechartsTooltip
                cursor={{ fill: 'hsl(var(--hover))' }}
                formatter={(value, name, item) => {
                  if (name === 'revenueBillion') {
                    const payload = item.payload as RevenueChartPoint;
                    return [
                      `${formatRevenueBillion(Number(value) * 100000000)} / ${formatGrowthPct(payload.revenueYoy)}`,
                      copy.revenue,
                    ];
                  }
                  return [String(value), String(name)];
                }}
                labelFormatter={(label) => `${copy.year}: ${label}`}
                contentStyle={{
                  background: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: 8,
                  color: 'hsl(var(--foreground))',
                }}
                labelStyle={{ color: 'hsl(var(--foreground))' }}
              />
              <Bar
                dataKey="revenueBillion"
                fill="var(--home-action-report-text)"
                name="revenueBillion"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
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
