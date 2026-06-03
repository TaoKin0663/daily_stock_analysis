import type React from 'react';
import { Cog, Network } from 'lucide-react';
import type { BusinessModelReport, ReportDetails, ReportLanguage } from '../../types/analysis';
import { isMeaningfulBusinessModelText } from '../../utils/businessModel';
import { normalizeReportLanguage } from '../../utils/reportLanguage';

interface BusinessModelSectionProps {
  details?: ReportDetails;
  language?: ReportLanguage;
  className?: string;
}

const normalizeText = (value?: string | null): string => (value || '').trim();

const getBusinessModel = (details?: ReportDetails): BusinessModelReport | undefined => {
  const model = details?.businessModel;
  const items = Array.isArray(model?.items)
    ? model.items
      .map((item) => ({
        title: normalizeText(item?.title),
        content: normalizeText(item?.content),
      }))
      .filter((item) => item.title && isMeaningfulBusinessModelText(item.content))
    : [];
  const summary = isMeaningfulBusinessModelText(model?.summary)
    ? normalizeText(model?.summary)
    : '';

  if (summary || items.length > 0) {
    return {
      summary,
      items,
      source: model?.source,
    };
  }

  return undefined;
};

export const BusinessModelSection: React.FC<BusinessModelSectionProps> = ({
  details,
  language,
  className = '',
}) => {
  const businessModel = getBusinessModel(details);
  const reportLanguage = normalizeReportLanguage(language);
  const copy = reportLanguage === 'en'
    ? {
      title: 'Business Model',
      summaryTitle: 'Core Business Model',
    }
    : {
      title: '业务模式',
      summaryTitle: '核心业务模式',
    };

  if (!businessModel) {
    return null;
  }

  return (
    <section className={className} aria-label={copy.title}>
      <div className="mb-3 flex items-center gap-2">
        <Network className="h-4 w-4 text-default-500" aria-hidden="true" />
        <h3 className="text-xs font-medium uppercase tracking-wider text-default-500">
          {copy.title}
        </h3>
      </div>

      {businessModel.items && businessModel.items.length > 0 ? (
        <ul className="space-y-3">
          {businessModel.items.map((item) => (
            <li key={`${item.title}-${item.content}`} className="flex gap-3 text-sm leading-6 text-foreground">
              <span className="mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-default-500" aria-hidden="true" />
              <div className="min-w-0">
                <span className="font-semibold">{item.title}</span>
                <span>：{item.content}</span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {businessModel.summary ? (
        <div className="mt-4 rounded-lg border border-subtle bg-default-50 px-4 py-3">
          <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Cog className="h-4 w-4 text-default-500" aria-hidden="true" />
            {copy.summaryTitle}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
            {businessModel.summary}
          </p>
        </div>
      ) : null}
    </section>
  );
};
