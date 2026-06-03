import type React from 'react';
import type {
  ReportDetails as ReportDetailsType,
  ReportMeta,
  ReportSummary as ReportSummaryType,
} from '../../types/analysis';
import { Badge, ScoreGauge } from '../common';
import { Card } from '@heroui/react/card';
import { Separator } from "@heroui/react";
import { formatDateTime } from '../../utils/format';
import { hasBusinessModelValue } from '../../utils/businessModel';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { BusinessModelSection } from './BusinessModelSection';
import { CompanyProfileSection } from './CompanyProfileSection';

interface ReportOverviewProps {
  meta: ReportMeta;
  summary: ReportSummaryType;
  details?: ReportDetailsType;
  isHistory?: boolean;
}

type BoardStatus = 'leading' | 'lagging';

type BoardSignal = {
  status: BoardStatus;
  changePct?: number;
};

const normalizeBoardName = (value?: string): string =>
  (value || '').trim().replace(/\s+/g, ' ');

const coerceFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim().replace(/%$/, '');
    if (!trimmed) {
      return undefined;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const buildBoardSignalMap = (details?: ReportDetailsType): Map<string, BoardSignal> => {
  const signalMap = new Map<string, BoardSignal>();
  const topBoards = Array.isArray(details?.sectorRankings?.top) ? details.sectorRankings.top : [];
  const bottomBoards = Array.isArray(details?.sectorRankings?.bottom) ? details.sectorRankings.bottom : [];

  topBoards.forEach((item) => {
    const normalizedName = normalizeBoardName(item?.name);
    if (!normalizedName) {
      return;
    }
    signalMap.set(normalizedName, {
      status: 'leading',
      changePct: coerceFiniteNumber(item.changePct),
    });
  });

  bottomBoards.forEach((item) => {
    const normalizedName = normalizeBoardName(item?.name);
    if (!normalizedName) {
      return;
    }
    signalMap.set(normalizedName, {
      status: 'lagging',
      changePct: coerceFiniteNumber(item.changePct),
    });
  });

  return signalMap;
};

const getIndustryFromBoards = (details?: ReportDetailsType): string | undefined => {
  const boards = Array.isArray(details?.belongBoards) ? details.belongBoards : [];
  const industryBoard = boards.find((board) => {
    const typeText = normalizeBoardName(board?.type).toLowerCase();
    return typeText.includes('行业') || typeText.includes('industry');
  });
  return normalizeBoardName(industryBoard?.name) || undefined;
};

const hasCompanyProfileValue = (details?: ReportDetailsType): boolean => {
  const profile = details?.companyProfile;
  if (!profile) {
    return Boolean(getIndustryFromBoards(details));
  }
  return Boolean(
    profile.fullName ||
    profile.industry ||
    profile.listingDate ||
    profile.totalShareCapital != null ||
    profile.floatShareCapital != null ||
    profile.employeeCount != null ||
    profile.website ||
    profile.mainBusiness ||
    profile.businessScope ||
    profile.companyIntro ||
    profile.legalRepresentative ||
    profile.actualController ||
    profile.directController ||
    profile.controlType ||
    getIndustryFromBoards(details),
  );
};

/**
 * 鎶ュ憡姒傝鍖虹粍浠?- 缁堢椋庢牸
 */
export const ReportOverview: React.FC<ReportOverviewProps> = ({
  meta,
  summary,
  details,
}) => {
  const reportLanguage = normalizeReportLanguage(meta.reportLanguage);
  const text = getReportText(reportLanguage);
  const relatedBoards = (Array.isArray(details?.belongBoards) ? details.belongBoards : [])
    .filter((board) => normalizeBoardName(board?.name).length > 0)
    .slice(0, 3);
  const boardSignals = buildBoardSignalMap(details);
  const shouldShowCompanyBasics = hasCompanyProfileValue(details);
  const shouldShowBusinessModel = hasBusinessModelValue(details);

  const getPriceChangeStyle = (changePct: number | undefined): React.CSSProperties | undefined => {
    if (changePct === undefined || changePct === null) {
      return undefined;
    }

    if (changePct > 0) {
      return { color: 'var(--home-price-up)' };
    }

    if (changePct < 0) {
      return { color: 'var(--home-price-down)' };
    }

    return undefined;
  };

  const formatChangePct = (changePct: number | undefined): string => {
    if (changePct === undefined || changePct === null) return '--';
    const sign = changePct > 0 ? '+' : '';
    return `${sign}${changePct.toFixed(2)}%`;
  };

  const getBoardStatusLabel = (status: BoardStatus): string => {
    if (status === 'leading') {
      return text.leadingBoard;
    }
    return text.laggingBoard;
  };

  const getBoardStatusVariant = (status: BoardStatus): 'success' | 'danger' => {
    if (status === 'leading') {
      return 'success';
    }
    return 'danger';
  };

  return (
    <div className="space-y-5">
      {/* 涓讳俊鎭尯 - 涓ゅ垪甯冨眬锛宨tems-stretch 纭繚鍙充晶涓庡乏渚у悓楂?*/}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-stretch">
        {/* 宸︿晶锛氳偂绁ㄤ俊鎭笌缁撹 */}
        <div className="lg:col-span-2 space-y-5">
          {/* 鑲＄エ澶撮儴 */}
          <Card>
            <Card.Content className="space-y-5">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h2 className="text-[28px] font-bold leading-tight text-foreground">
                      {meta.stockName || meta.stockCode}
                    </h2>
                    {meta.currentPrice != null && (
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-bold font-mono" style={getPriceChangeStyle(meta.changePct)}>
                          {meta.currentPrice.toFixed(2)}
                        </span>
                        <span className="text-sm font-semibold font-mono" style={getPriceChangeStyle(meta.changePct)}>
                          {formatChangePct(meta.changePct)}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="rounded-md bg-default-100 px-2 py-0.5 font-mono text-xs text-default-600">
                      {meta.stockCode}
                    </span>
                    <span className="text-xs text-default-400 flex items-center gap-1">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {formatDateTime(meta.createdAt)}
                    </span>
                  </div>
                </div>
              </div>
              <Separator />
              {(shouldShowCompanyBasics || shouldShowBusinessModel) && (
                <>
                  {shouldShowCompanyBasics ? (
                    <CompanyProfileSection details={details} language={reportLanguage} />
                  ) : null}
                  {shouldShowBusinessModel ? (
                    <BusinessModelSection
                      details={details}
                      language={reportLanguage}
                      className={shouldShowCompanyBasics ? 'mt-5 border-t border-subtle pt-5' : ''}
                    />
                  ) : null}
                  <Separator />
                </>
              )}
              <div>
                <Card.Title className="mb-2 text-xs font-medium uppercase tracking-wider text-default-500">
                  {text.keyInsights}
                </Card.Title>
                <p className="max-w-[62ch] whitespace-pre-wrap text-left text-[15px] leading-7 text-foreground">
                  {summary.analysisSummary || text.noAnalysisSummary}
                </p>
              </div>
            </Card.Content>
          </Card>

          {/* 鎿嶄綔寤鸿鍜岃秼鍔块娴?*/}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 鎿嶄綔寤鸿 */}
            <Card>
              <Card.Content className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-full h-full text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div className="space-y-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-[0.16em] text-default-500">{text.actionAdvice}</h4>
                  <p className="text-sm leading-6 text-foreground">
                    {summary.operationAdvice || text.noAdvice}
                  </p>
                </div>
              </Card.Content>
            </Card>

            {/* 瓒嬪娍棰勬祴 */}
            <Card>
              <Card.Content className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-full h-full text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div className="space-y-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-[0.16em] text-default-500">{text.trendPrediction}</h4>
                  <p className="text-sm leading-6 text-foreground">
                    {summary.trendPrediction || text.noPrediction}
                  </p>
                </div>
              </Card.Content>
            </Card>
          </div>

          {relatedBoards.length > 0 && (
            <Card>
              <Card.Header className="flex items-baseline gap-2 pb-0">
                <span className="text-xs font-medium uppercase tracking-wider text-default-500">{text.boardLinkage}</span>
                <Card.Title className="text-base font-semibold text-foreground">{text.relatedBoards}</Card.Title>
              </Card.Header>
              <Card.Content className="space-y-2.5">
                {relatedBoards.map((board, index) => {
                  const boardName = normalizeBoardName(board.name);
                  const signal = boardSignals.get(boardName);
                  return (
                    <div
                      key={`${boardName}-${board.code || index}`}
                      className="flex flex-wrap items-center gap-2 text-sm"
                    >
                      <span className="rounded-md bg-default-100 px-2 py-0.5 text-xs font-medium text-default-700">
                        {boardName}
                      </span>
                      {board.type && (
                        <span className="rounded-full bg-default-100 px-2 py-0.5 text-xs text-default-600">
                          {board.type}
                        </span>
                      )}
                      {signal && (
                        <Badge
                          variant={getBoardStatusVariant(signal.status)}
                          className="shadow-none"
                        >
                          {getBoardStatusLabel(signal.status)}
                        </Badge>
                      )}
                      {signal && signal.changePct !== undefined && signal.changePct !== null && (
                        <span
                          className="text-xs font-mono"
                          style={getPriceChangeStyle(signal.changePct)}
                        >
                          {formatChangePct(signal.changePct)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </Card.Content>
            </Card>
          )}
        </div>

        {/* 鍙充晶锛氭儏缁寚鏍?*/}
        <div className="flex flex-col self-stretch min-h-full">
          <Card className="flex-1 flex flex-col">
            <Card.Content className="flex flex-col items-center justify-center flex-1 p-6">
              <Card.Title className="mb-5 text-sm font-medium tracking-wide text-foreground">{text.marketSentiment}</Card.Title>
              <ScoreGauge score={summary.sentimentScore} size="lg" language={reportLanguage} />
            </Card.Content>
          </Card>
        </div>
      </div>
    </div>
  );
};
