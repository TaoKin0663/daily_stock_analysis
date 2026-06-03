import type { ReportDetails } from '../types/analysis';

const normalizeBoardName = (value?: string): string =>
  (value || '').trim().replace(/\s+/g, ' ');

export const getIndustryFromBoards = (details?: ReportDetails): string | undefined => {
  const boards = Array.isArray(details?.belongBoards) ? details.belongBoards : [];
  const industryBoard = boards.find((board) => {
    const typeText = normalizeBoardName(board?.type).toLowerCase();
    return typeText.includes('行业') || typeText.includes('industry');
  });
  return normalizeBoardName(industryBoard?.name) || undefined;
};

export const hasCompanyProfileValue = (details?: ReportDetails): boolean => {
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
