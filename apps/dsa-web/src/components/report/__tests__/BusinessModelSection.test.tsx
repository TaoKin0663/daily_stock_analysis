import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BusinessModelSection } from '../BusinessModelSection';

describe('BusinessModelSection', () => {
  it('renders dynamic business model dimensions from structured data', () => {
    render(
      <BusinessModelSection
        language="zh"
        details={{
          businessModel: {
            summary: '公司通过算力基础设施和云服务订阅形成持续收入。',
            items: [
              {
                title: '收入结构',
                content: '核心收入来自云资源租用、增值服务和企业客户长期合约。',
              },
              {
                title: '客户获取',
                content: '通过渠道伙伴和直销团队服务大型企业客户。',
              },
            ],
            source: 'llm',
          },
        }}
      />,
    );

    expect(screen.getByText('业务模式')).toBeInTheDocument();
    expect(screen.getByText('收入结构')).toBeInTheDocument();
    expect(screen.getByText(/核心收入来自云资源租用/)).toBeInTheDocument();
    expect(screen.getByText('客户获取')).toBeInTheDocument();
    expect(screen.getByText('核心业务模式')).toBeInTheDocument();
    expect(screen.getByText('公司通过算力基础设施和云服务订阅形成持续收入。')).toBeInTheDocument();
  });

  it('does not fall back to company profile text when structured data is missing', () => {
    const { container } = render(
      <BusinessModelSection
        language="en"
        details={{
          companyProfile: {
            mainBusiness: 'The company operates retail banking and wealth management services.',
          },
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('does not render when there is no business model signal', () => {
    const { container } = render(<BusinessModelSection details={{}} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('does not render placeholder business model text', () => {
    const { container } = render(
      <BusinessModelSection
        details={{
          businessModel: {
            summary: '数据缺失，无法判断具体业务模式。',
            items: [
              { title: '主营业务与收入来源', content: '数据缺失，无法判断。' },
              { title: '盈利模式与成本结构', content: '数据缺失，无法判断。' },
            ],
          },
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('filters invalid items while preserving meaningful business model content', () => {
    render(
      <BusinessModelSection
        language="en"
        details={{
          businessModel: {
            summary: 'The company earns recurring revenue from enterprise cloud subscriptions.',
            items: [
              { title: 'Revenue model', content: 'Subscription and usage fees anchor recurring revenue.' },
              { title: 'Cost structure', content: 'Data unavailable, cannot determine.' },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText('Revenue model')).toBeInTheDocument();
    expect(screen.getByText(/Subscription and usage fees/)).toBeInTheDocument();
    expect(screen.queryByText('Cost structure')).not.toBeInTheDocument();
    expect(screen.queryByText(/Data unavailable/)).not.toBeInTheDocument();
  });
});
