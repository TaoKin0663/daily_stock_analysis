import type React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FinancialProfitabilitySection } from '../FinancialProfitabilitySection';

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="profitability-chart">{children}</div>
  ),
  Area: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('FinancialProfitabilitySection', () => {
  it('renders LLM profitability analysis and keeps gross margin trend chart', () => {
    render(
      <FinancialProfitabilitySection
        financialReport={{
          profitability: {
            source: 'stock_financial_analysis_indicator_em',
            unit: 'percent',
            rows: [
              { period: '2025-12-31', grossMargin: 42.61, netMargin: 28.2, roe: 43.84 },
              { period: '2024-12-31', grossMargin: 38.2, netMargin: 25.1, roe: 32.5 },
            ],
          },
        }}
        profitabilityAnalysis={{
          summary: '公司盈利能力持续提升，2025年毛利率达42.61%。',
          items: [
            {
              title: '高端产品驱动',
              content: '高端产品占比提升带动毛利率改善。',
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('盈利能力')).toBeInTheDocument();
    expect(screen.queryByText('报告期')).not.toBeInTheDocument();
    expect(screen.getByText(/公司盈利能力持续提升/)).toBeInTheDocument();
    expect(screen.getByText('高端产品驱动：')).toBeInTheDocument();
    expect(screen.getByText('高端产品占比提升带动毛利率改善。')).toBeInTheDocument();
    expect(screen.getByText('盈利能力趋势（毛利率）')).toBeInTheDocument();
    expect(screen.getByLabelText('盈利能力趋势毛利率图表')).toBeInTheDocument();
    expect(screen.getByTestId('profitability-chart')).toBeInTheDocument();
  });

  it('renders fallback metrics text when LLM profitability analysis is missing', () => {
    render(
      <FinancialProfitabilitySection
        financialReport={{
          profitability: {
            rows: [
              { period: '2025-12-31', grossMargin: 42.61, netMargin: 28.2, roe: 43.84 },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText('盈利能力')).toBeInTheDocument();
    expect(screen.getByText(/2025-12-31 盈利能力指标/)).toBeInTheDocument();
    expect(screen.getByText(/毛利率 42.61%/)).toBeInTheDocument();
    expect(screen.getByText('盈利能力趋势（毛利率）')).toBeInTheDocument();
  });

  it('supports snake_case profitability rows from backend payloads', () => {
    render(
      <FinancialProfitabilitySection
        financialReport={{
          profitability: {
            rows: [
              {
                period: '2025-12-31',
                gross_margin: '42.61',
                net_margin: '28.20',
                roe: 43.84,
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText(/毛利率 42.61%/)).toBeInTheDocument();
    expect(screen.getByTestId('profitability-chart')).toBeInTheDocument();
  });

  it('renders fallback metrics from top-level financial report when profitability rows are missing', () => {
    render(
      <FinancialProfitabilitySection
        financialReport={{
          reportDate: '2025-12-31',
          grossMargin: 42.61,
          netMargin: 28.2,
          roe: 43.84,
        }}
      />,
    );

    expect(screen.getByText(/2025-12-31 盈利能力指标/)).toBeInTheDocument();
    expect(screen.getByText(/净利率 28.20%/)).toBeInTheDocument();
  });

  it('renders nothing when profitability rows, metrics, and analysis are missing', () => {
    const { container } = render(<FinancialProfitabilitySection financialReport={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
