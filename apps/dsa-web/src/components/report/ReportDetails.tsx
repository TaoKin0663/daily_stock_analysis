import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import type { ReportDetails as ReportDetailsType, ReportLanguage } from '../../types/analysis';
import { Card } from '@heroui/react/card';
import { Separator } from "@heroui/react";
import { DashboardPanelHeader } from '../dashboard';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportDetailsProps {
  details?: ReportDetailsType;
  recordId?: number;  // 分析历史记录主键 ID
  language?: ReportLanguage;
}

/**
 * 透明度与追溯区组件 - 终端风格
 */
export const ReportDetails: React.FC<ReportDetailsProps> = ({
  details,
  recordId,
  language = 'zh',
}) => {
  type JsonPanel = 'raw' | 'snapshot';
  type CopiedPanelState = Record<JsonPanel, boolean>;

  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const [showRaw, setShowRaw] = useState(false);
  const [showSnapshot, setShowSnapshot] = useState(false);
  const [copiedPanels, setCopiedPanels] = useState<CopiedPanelState>({
    raw: false,
    snapshot: false,
  });
  const copyResetTimerRef = useRef<Partial<Record<JsonPanel, number>>>({});

  useEffect(() => {
    return () => {
      Object.values(copyResetTimerRef.current).forEach((timerId) => {
        if (timerId !== undefined) {
          window.clearTimeout(timerId);
        }
      });
      copyResetTimerRef.current = {};
    };
  }, []);

  if (!details?.rawResult && !details?.contextSnapshot && !recordId) {
    return null;
  }

  const copyToClipboard = async (content: string, panel: JsonPanel) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedPanels((prev) => ({
        ...prev,
        [panel]: true,
      }));
      const existingTimer = copyResetTimerRef.current[panel];
      if (existingTimer !== undefined) {
        window.clearTimeout(existingTimer);
      }
      copyResetTimerRef.current[panel] = window.setTimeout(() => {
        setCopiedPanels((prev) => ({
          ...prev,
          [panel]: false,
        }));
        delete copyResetTimerRef.current[panel];
      }, 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  const renderJson = (data: unknown, panel: JsonPanel) => {
    const jsonStr = JSON.stringify(data, null, 2);
    return (
      <div className="relative overflow-hidden">
        <span className="absolute top-2 right-2 z-10 inline-flex">
          <button
            type="button"
            onClick={() => copyToClipboard(jsonStr, panel)}
            className="text-xs text-default-400 hover:text-foreground transition-colors"
            aria-label={copiedPanels[panel] ? text.copied : text.copy}
          >
            {copiedPanels[panel] ? text.copied : text.copy}
          </button>
        </span>
        <pre className="text-xs text-foreground font-mono overflow-x-auto p-3 bg-default-50 rounded-lg max-h-80 overflow-y-auto text-left w-0 min-w-full">
          {jsonStr}
        </pre>
      </div>
    );
  };

  return (
    <Card className="text-left">
      <Card.Header className="pb-0">
        <DashboardPanelHeader
          eyebrow={text.transparency}
          title={text.traceability}
        />
      </Card.Header>
      <Card.Content className="space-y-3">
        {/* Record ID */}
        {recordId && (
          <>
            <div className="flex items-center gap-2 text-xs text-default-400">
              <span>{text.recordId}:</span>
              <code className="rounded bg-default-100 px-1.5 py-0.5 font-mono text-xs text-default-700">
                {recordId}
              </code>
            </div>
            <Separator />
          </>
        )}

        {/* 折叠区域 */}
        <div className="space-y-2">
          {/* 原始分析结果 */}
          {details?.rawResult && (
            <div>
              <button
                type="button"
                onClick={() => setShowRaw(!showRaw)}
                className="flex w-full items-center justify-between rounded-lg bg-default-50 p-2.5 transition-colors hover:bg-default-100"
              >
                <span className="text-xs text-foreground">{text.rawResult}</span>
                <svg
                  className={`w-3.5 h-3.5 text-default-400 transition-transform ${showRaw ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showRaw && (
                <div className="mt-2 animate-fade-in min-w-0 overflow-hidden">
                  {renderJson(details.rawResult, 'raw')}
                </div>
              )}
            </div>
          )}

          {/* 分析快照 */}
          {details?.contextSnapshot && (
            <div>
              <button
                type="button"
                onClick={() => setShowSnapshot(!showSnapshot)}
                className="flex w-full items-center justify-between rounded-lg bg-default-50 p-2.5 transition-colors hover:bg-default-100"
              >
                <span className="text-xs text-foreground">{text.analysisSnapshot}</span>
                <svg
                  className={`w-3.5 h-3.5 text-default-400 transition-transform ${showSnapshot ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showSnapshot && (
                <div className="mt-2 animate-fade-in min-w-0 overflow-hidden">
                  {renderJson(details.contextSnapshot, 'snapshot')}
                </div>
              )}
            </div>
          )}
        </div>
      </Card.Content>
    </Card>
  );
};
