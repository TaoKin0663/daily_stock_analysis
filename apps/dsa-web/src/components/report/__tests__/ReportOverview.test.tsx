import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportOverview } from '../ReportOverview';

const baseMeta = {
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  reportType: 'detailed' as const,
  reportLanguage: 'zh' as const,
  createdAt: '2026-03-21T08:00:00Z',
};

const baseSummary = {
  analysisSummary: '趋势维持强势',
  operationAdvice: '继续观察买点',
  trendPrediction: '短线震荡偏强',
  sentimentScore: 78,
};

describe('ReportOverview', () => {
  it('renders company profile basics with website link', () => {
    render(
      <ReportOverview
        meta={{ ...baseMeta, reportLanguage: 'en', stockName: 'Apple' }}
        summary={baseSummary}
        details={{
          companyProfile: {
            fullName: 'Apple Inc.',
            industry: 'Consumer Electronics',
            legalRepresentative: 'Tim Cook',
            listingDate: '1980-12-12',
            totalShareCapital: 15000000000,
            floatShareCapital: 14900000000,
            employeeCount: 164000,
            website: 'www.apple.com',
            companyIntro: 'Apple designs consumer technology products and services.',
            actualController: 'Public shareholders',
            actualControllerHoldRatio: 12.25,
            directController: 'Board of Directors',
            controlType: 'Public company',
          },
        }}
      />,
    );

    expect(screen.getByText('Company Basics')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Consumer Electronics')).toBeInTheDocument();
    expect(screen.getByText('1980-12-12')).toBeInTheDocument();
    expect(screen.getByText('Company Introduction')).toBeInTheDocument();
    expect(screen.getByText('Apple designs consumer technology products and services.')).toBeInTheDocument();
    expect(screen.getByText('Core Management')).toBeInTheDocument();
    expect(screen.getByText('Tim Cook')).toBeInTheDocument();
    expect(screen.getByText('Public shareholders (Holding approx. 12.25%)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /www\.apple\.com/i })).toHaveAttribute(
      'href',
      'https://www.apple.com',
    );
  });

  it('renders business model section with dynamic dimensions', () => {
    render(
      <ReportOverview
        meta={{ ...baseMeta, reportLanguage: 'en', stockName: 'CloudCo' }}
        summary={baseSummary}
        details={{
          businessModel: {
            summary: 'CloudCo monetizes enterprise cloud infrastructure through subscriptions.',
            items: [
              {
                title: 'Revenue mix',
                content: 'Subscription contracts and usage-based services provide recurring revenue.',
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText('Business Model')).toBeInTheDocument();
    expect(screen.getByText('Revenue mix')).toBeInTheDocument();
    expect(screen.getByText(/usage-based services/)).toBeInTheDocument();
    expect(screen.getByText('Core Business Model')).toBeInTheDocument();
  });

  it('uses industry board as company basics fallback', () => {
    render(
      <ReportOverview
        meta={{ ...baseMeta, reportLanguage: 'en' }}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: 'Semiconductors', type: 'Industry' }],
        }}
      />,
    );

    expect(screen.getByText('Company Basics')).toBeInTheDocument();
    expect(screen.getAllByText('Semiconductors').length).toBeGreaterThan(0);
  });

  it('uses Chinese industry board as company basics fallback', () => {
    render(
      <ReportOverview
        meta={{ ...baseMeta, reportLanguage: 'en' }}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: 'Baijiu', type: '行业' }],
        }}
      />,
    );

    expect(screen.getByText('Company Basics')).toBeInTheDocument();
    expect(screen.getAllByText('Baijiu').length).toBeGreaterThan(0);
  });

  it('renders related boards with leading and lagging markers', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: ' 白酒 ', type: '行业' },
            { name: '消费', type: '概念' },
            { name: '新能源' },
          ],
          sectorRankings: {
            top: [{ name: '白酒', changePct: 2.31 }],
            bottom: [{ name: '消费', changePct: -1.2 }],
          },
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getAllByText('白酒').length).toBeGreaterThan(0);
    expect(screen.getByText('行业')).toBeInTheDocument();
    expect(screen.getByText('领涨')).toBeInTheDocument();
    expect(screen.getByText('+2.31%')).toBeInTheDocument();
    expect(screen.getByText('领跌')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
    expect(screen.queryByText('中性')).not.toBeInTheDocument();
  });

  it('shows board list when rankings are unavailable', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: '半导体', type: '行业' }],
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getAllByText('半导体').length).toBeGreaterThan(0);
    expect(screen.queryByText('中性')).not.toBeInTheDocument();
    expect(screen.queryByText('领涨')).not.toBeInTheDocument();
    expect(screen.queryByText('领跌')).not.toBeInTheDocument();
  });

  it('hides related boards section when no boards are available', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);

    expect(screen.queryByText('关联板块')).not.toBeInTheDocument();
  });

  it('fails open on malformed ranking payloads', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: ' 白酒 ' }],
          sectorRankings: {
            top: {} as unknown as never[],
            bottom: [{ name: '白酒', changePct: '-2.5%' as unknown as number }],
          },
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getByText('白酒')).toBeInTheDocument();
    expect(screen.getByText('领跌')).toBeInTheDocument();
    expect(screen.getByText('-2.50%')).toBeInTheDocument();
  });
});
