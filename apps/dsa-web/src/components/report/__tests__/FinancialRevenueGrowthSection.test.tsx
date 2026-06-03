import type React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FinancialRevenueGrowthSection } from '../FinancialRevenueGrowthSection';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="revenue-growth-chart">{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('FinancialRevenueGrowthSection', () => {
  it('renders annual revenue growth rows and chart in CNY billion', () => {
    render(
      <FinancialRevenueGrowthSection
        financialReport={{
          revenueGrowth: {
            source: 'stock_lrb_em',
            unit: 'yuan',
            frequency: 'annual',
            rows: [
              { fiscalYear: 2025, revenue: 15000000000, revenueYoy: 12.5 },
              { fiscalYear: 2024, revenue: 12000000000, revenueYoy: -3.25 },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText('营收增长')).toBeInTheDocument();
    expect(screen.getByText('年度')).toBeInTheDocument();
    expect(screen.getByText('营业收入（亿）')).toBeInTheDocument();
    expect(screen.getByText('同比增长率')).toBeInTheDocument();
    expect(screen.getByLabelText('营收增长数据图表')).toBeInTheDocument();
    expect(screen.getByTestId('revenue-growth-chart')).toBeInTheDocument();
    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('150.00')).toBeInTheDocument();
    expect(screen.getByText('+12.50%')).toBeInTheDocument();
    expect(screen.getByText('-3.25%')).toBeInTheDocument();
  });

  it('renders nothing when revenue growth rows are missing', () => {
    const { container } = render(<FinancialRevenueGrowthSection financialReport={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
