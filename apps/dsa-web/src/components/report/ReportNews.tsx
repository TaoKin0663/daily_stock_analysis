import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { ApiErrorAlert } from '../common';
import { Card } from '@heroui/react/card';
import { Link } from '@heroui/react';
import { DashboardPanelHeader, DashboardStateBlock } from '../dashboard';
import { historyApi } from '../../api/history';
import type { NewsIntelItem, ReportLanguage } from '../../types/analysis';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportNewsProps {
  recordId?: number;  // 分析历史记录主键 ID
  limit?: number;
  language?: ReportLanguage;
}

/**
 * 资讯区组件 - 终端风格
 */
export const ReportNews: React.FC<ReportNewsProps> = ({ recordId, limit = 8, language = 'zh' }) => {
  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const [isLoading, setIsLoading] = useState(false);
  const [items, setItems] = useState<NewsIntelItem[]>([]);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const fetchNews = useCallback(async () => {
    if (!recordId) return;
    setIsLoading(true);
    setError(null);

    try {
      const response = await historyApi.getNews(recordId, limit);
      setItems(response.items || []);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [recordId, limit]);

  useEffect(() => {
    setItems([]);
    setError(null);

    if (recordId) {
      fetchNews();
    }
  }, [recordId, fetchNews]);

  if (!recordId) {
    return null;
  }

  return (
    <Card>
      <Card.Header className="pb-0">
        <DashboardPanelHeader
          eyebrow={text.newsFeed}
          title={text.relatedNews}
          actions={(
            <div className="flex items-center gap-2">
              {isLoading ? (
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-default-300 border-t-primary" aria-hidden="true" />
              ) : null}
              <button
                type="button"
                onClick={() => void fetchNews()}
                className="text-xs text-primary hover:underline"
                aria-label={text.refresh}
              >
                {text.refresh}
              </button>
            </div>
          )}
        />
      </Card.Header>
      <Card.Content className="pt-0">
        {error && !isLoading && (
          <ApiErrorAlert
            error={error}
            actionLabel={text.retry}
            onAction={() => void fetchNews()}
            dismissLabel={text.dismiss}
          />
        )}

        {isLoading && !error && (
          <DashboardStateBlock
            compact
            loading
            title={text.loadingNews}
          />
        )}

        {!isLoading && !error && items.length === 0 && (
          <DashboardStateBlock
            compact
            title={text.noNews}
            description={text.noNewsDescription}
            icon={(
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 14l-7-7m0 0l-7 7m7-7v18" />
              </svg>
            )}
          />
        )}

        {!isLoading && !error && items.length > 0 && (
          <div className="space-y-3 text-left">
            {items.map((item, index) => (
              <div
                key={`${item.title}-${index}`}
                className="rounded-xl bg-default-50 p-4 transition-colors hover:bg-default-100"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-sm font-medium leading-6 text-foreground text-left">
                      {
                        item.url ? (
                          <Link href={item.url} target='_blank'>
                            {item.title}
                          </Link>
                        ) : <>{item.title}</>
                      }
                    </p>
                    {item.snippet && (
                      <p className="mt-2 text-sm leading-6 text-default-500 text-left overflow-hidden [display:-webkit-box] [-webkit-line-clamp:3] [-webkit-box-orient:vertical]">
                        {item.snippet}
                      </p>
                    )}
                  </div>
                  {/* {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 shrink-0 whitespace-nowrap rounded-full bg-default-100 px-2.5 py-1 text-xs text-default-600 transition-colors hover:bg-default-200 hover:text-foreground"
                      aria-label={text.openLink}
                    >
                      {text.openLink}
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M14 3h7m0 0v7m0-7L10 14"
                        />
                      </svg>
                    </a>
                  )} */}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card.Content>
    </Card>
  );
};
