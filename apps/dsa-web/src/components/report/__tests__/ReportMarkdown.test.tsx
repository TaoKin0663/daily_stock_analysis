import type React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import { ReportMarkdown } from '../ReportMarkdown';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getMarkdown: vi.fn(),
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

describe('ReportMarkdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses localized copy labels for English reports', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    render(
      <ReportMarkdown
        recordId={1}
        stockName="Apple"
        stockCode="AAPL"
        reportLanguage="en"
        onClose={() => {}}
      />
    );

    expect(await screen.findByRole('button', { name: 'Copy Markdown Source' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Plain Text' })).toBeInTheDocument();
  });

  it('renders company profile before markdown content', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    render(
      <ReportMarkdown
        recordId={1}
        stockName="Apple"
        stockCode="AAPL"
        reportLanguage="en"
        details={{
          companyProfile: {
            fullName: 'Apple Inc.',
            industry: 'Consumer Electronics',
            legalRepresentative: 'Tim Cook',
            companyIntro: 'Apple designs consumer technology products and services.',
            actualController: 'Public shareholders',
          },
        }}
        onClose={() => {}}
      />,
    );

    expect(await screen.findByText('Company Basics')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Company Introduction')).toBeInTheDocument();
    expect(screen.getByText('Apple designs consumer technology products and services.')).toBeInTheDocument();
    expect(screen.getByText('Core Management')).toBeInTheDocument();
    expect(screen.getByText('Tim Cook')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Full report' })).toBeInTheDocument();
  });

  it('renders business model before markdown content', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    render(
      <ReportMarkdown
        recordId={1}
        stockName="CloudCo"
        stockCode="CLOUD"
        reportLanguage="en"
        details={{
          businessModel: {
            summary: 'CloudCo sells recurring cloud infrastructure services.',
            items: [
              {
                title: 'Commercial model',
                content: 'Enterprise subscriptions and usage fees anchor revenue.',
              },
            ],
          },
        }}
        onClose={() => {}}
      />,
    );

    expect(await screen.findByText('Business Model')).toBeInTheDocument();
    expect(screen.getByText('Commercial model')).toBeInTheDocument();
    expect(screen.getByText(/Enterprise subscriptions/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Full report' })).toBeInTheDocument();
  });

  it('renders profitability before markdown content', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    render(
      <ReportMarkdown
        recordId={1}
        stockName="Apple"
        stockCode="AAPL"
        reportLanguage="zh"
        details={{
          financialReport: {
            profitability: {
              rows: [
                { period: '2025-12-31', grossMargin: 42.61, netMargin: 28.2, roe: 43.84 },
              ],
            },
          },
          profitabilityAnalysis: {
            summary: '公司盈利能力持续提升，2025年毛利率达42.61%。',
            items: [{ title: '成本控制', content: '净利率和ROE维持高位。' }],
          },
        }}
        onClose={() => {}}
      />,
    );

    expect(await screen.findByText('盈利能力')).toBeInTheDocument();
    expect(screen.getByText(/公司盈利能力持续提升/)).toBeInTheDocument();
    expect(screen.getByText('成本控制：')).toBeInTheDocument();
    expect(screen.getByText('盈利能力趋势（毛利率）')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Full report' })).toBeInTheDocument();
  });

  it('opens a printable full report document for PDF saving', async () => {
    const print = vi.fn();
    const printDocument = {
      readyState: 'complete',
      write: vi.fn(),
      close: vi.fn(),
    };
    const printWindow = {
      document: printDocument,
      focus: vi.fn(),
      print,
      addEventListener: vi.fn(),
    };
    const open = vi.fn(() => printWindow);
    Object.defineProperty(window, 'open', {
      configurable: true,
      value: open,
    });
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    render(
      <ReportMarkdown
        recordId={1}
        stockName="Apple"
        stockCode="AAPL"
        reportLanguage="en"
        onClose={() => {}}
      />,
    );

    const savePdfButton = await screen.findByRole('button', { name: 'Save as PDF' });
    fireEvent.click(savePdfButton);

    expect(open).toHaveBeenCalledWith('', '_blank', 'width=900,height=1200');
    expect(printDocument.write).toHaveBeenCalledWith(expect.stringContaining('Full report'));
    await waitFor(() => expect(print).toHaveBeenCalledTimes(1));
  });
});
