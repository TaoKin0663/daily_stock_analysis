import type React from 'react';
import { Building2, ExternalLink, FileText, UsersRound } from 'lucide-react';
import type { ReportDetails, ReportLanguage } from '../../types/analysis';
import { getIndustryFromBoards, hasCompanyProfileValue } from '../../utils/companyProfile';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

const normalizeWebsiteHref = (value?: string): string | undefined => {
  const website = (value || '').trim();
  if (!website) {
    return undefined;
  }
  if (/^https?:\/\//i.test(website)) {
    return website;
  }
  return `https://${website}`;
};

interface CompanyProfileSectionProps {
  details?: ReportDetails;
  language?: ReportLanguage;
  className?: string;
}

export const CompanyProfileSection: React.FC<CompanyProfileSectionProps> = ({
  details,
  language,
  className = '',
}) => {
  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const profile = details?.companyProfile;
  const fallbackIndustry = getIndustryFromBoards(details);
  const websiteHref = normalizeWebsiteHref(profile?.website);

  if (!hasCompanyProfileValue(details)) {
    return null;
  }

  const formatCount = (value: number | undefined): string => {
    if (value === undefined || value === null || !Number.isFinite(value)) {
      return '--';
    }
    return new Intl.NumberFormat(reportLanguage === 'en' ? 'en-US' : 'zh-CN', {
      notation: 'compact',
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatRatio = (value: number | undefined): string | undefined => {
    if (value === undefined || value === null || !Number.isFinite(value)) {
      return undefined;
    }
    return `${value.toFixed(2).replace(/\.?0+$/, '')}%`;
  };

  const companyIntro = profile?.companyIntro || profile?.mainBusiness || profile?.businessScope;
  const companyBasics = [
    { label: text.fullName, value: profile?.fullName || '--' },
    { label: text.industry, value: profile?.industry || fallbackIndustry || '--' },
    { label: text.listingDate, value: profile?.listingDate || '--' },
    { label: text.totalShareCapital, value: formatCount(profile?.totalShareCapital) },
    { label: text.floatShareCapital, value: formatCount(profile?.floatShareCapital) },
    { label: text.employeeCount, value: formatCount(profile?.employeeCount) },
  ];
  const actualControllerText = profile?.actualController
    ? [
      profile.actualController,
      formatRatio(profile.actualControllerHoldRatio)
        ? `(${text.holdRatioApprox}${formatRatio(profile.actualControllerHoldRatio)})`
        : undefined,
    ].filter(Boolean).join(' ')
    : '--';
  const coreManagement = [
    { label: text.legalRepresentative, value: profile?.legalRepresentative || '--' },
    { label: text.actualController, value: actualControllerText },
    { label: text.directController, value: profile?.directController || '--' },
    { label: text.controlType, value: profile?.controlType || '--' },
  ];

  return (
    <div className={className}>
      <div className="mb-3 flex items-center gap-2">
        <Building2 className="h-4 w-4 text-default-500" aria-hidden="true" />
        <h3 className="text-xs font-medium uppercase tracking-wider text-default-500">
          {text.companyBasics}
        </h3>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {companyBasics.map((item) => (
          <div
            key={item.label}
            className="min-w-0 rounded-lg bg-default-50 px-3 py-2.5"
          >
            <div className="text-[11px] font-medium uppercase tracking-wide text-default-500">
              {item.label}
            </div>
            <div className="mt-1 truncate text-sm font-medium text-foreground" title={item.value}>
              {item.value}
            </div>
          </div>
        ))}
        <div className="min-w-0 rounded-lg bg-default-50 px-3 py-2.5">
          <div className="text-[11px] font-medium uppercase tracking-wide text-default-500">
            {text.website}
          </div>
          {profile?.website && websiteHref ? (
            <a
              href={websiteHref}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex max-w-full items-center gap-1 text-sm font-medium text-primary hover:text-primary-600"
              title={profile.website}
            >
              <span className="truncate">{profile.website}</span>
              <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            </a>
          ) : (
            <div className="mt-1 text-sm font-medium text-foreground">--</div>
          )}
        </div>
      </div>
      {companyIntro && (
        <div className="mt-4 rounded-lg bg-default-50 px-3 py-3">
          <div className="mb-1.5 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-default-500">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            {text.companyIntro}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
            {companyIntro}
          </p>
        </div>
      )}
      <div className="mt-4">
        <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-default-500">
          <UsersRound className="h-3.5 w-3.5" aria-hidden="true" />
          {text.coreManagement}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {coreManagement.map((item) => (
            <div
              key={item.label}
              className="min-w-0 rounded-lg bg-default-50 px-3 py-2.5"
            >
              <div className="text-[11px] font-medium uppercase tracking-wide text-default-500">
                {item.label}
              </div>
              <div className="mt-1 truncate text-sm font-medium text-foreground" title={item.value}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
