import type { ReportDetails } from '../types/analysis';

const normalizeText = (value?: string | null): string => (value || '').trim();

const INVALID_BUSINESS_MODEL_PATTERNS = [
  /数据缺失/,
  /无法判断/,
  /无法判定/,
  /暂无/,
  /无足够/,
  /信息不足/,
  /资料不足/,
  /^n\/?a$/i,
  /^none$/i,
  /^null$/i,
  /insufficient data/i,
  /data (is )?(missing|unavailable|insufficient)/i,
  /cannot (determine|judge|assess)/i,
  /not enough (data|information)/i,
  /not available/i,
];

export const isMeaningfulBusinessModelText = (value?: string | null): boolean => {
  const text = normalizeText(value);
  if (!text) {
    return false;
  }
  return !INVALID_BUSINESS_MODEL_PATTERNS.some((pattern) => pattern.test(text));
};

export const hasBusinessModelValue = (details?: ReportDetails): boolean => {
  const model = details?.businessModel;
  if (!model) {
    return false;
  }

  const hasSummary = isMeaningfulBusinessModelText(model.summary);
  const hasItems = Array.isArray(model.items)
    && model.items.some((item) => normalizeText(item?.title) && isMeaningfulBusinessModelText(item?.content));

  return hasSummary || hasItems;
};
