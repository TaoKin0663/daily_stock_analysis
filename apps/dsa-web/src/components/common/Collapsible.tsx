import React from 'react';
import { DisclosureRoot, DisclosureHeading, DisclosureTrigger, DisclosureContent, DisclosureBody, DisclosureIndicator } from '@heroui/react/disclosure';
import { cn } from '../../utils/cn';

interface CollapsibleProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  icon?: React.ReactNode;
  className?: string;
}

export const Collapsible: React.FC<CollapsibleProps> = ({
  title,
  children,
  defaultOpen = false,
  icon,
  className = '',
}) => {
  return (
    <DisclosureRoot defaultExpanded={defaultOpen} className={cn('rounded-2xl border border-subtle bg-card/70 shadow-soft-card', className)}>
      <DisclosureHeading>
        <DisclosureTrigger className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-hover rounded-2xl group-data-[expanded]:rounded-b-none">
          <div className="flex items-center gap-3">
            {icon && <span className="text-cyan">{icon}</span>}
            <span className="font-medium text-foreground text-sm">{title}</span>
          </div>
          <DisclosureIndicator>
            <svg className="h-5 w-5 text-secondary-text transition-transform duration-300 group-data-[expanded]:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </DisclosureIndicator>
        </DisclosureTrigger>
      </DisclosureHeading>
      <DisclosureContent>
        <DisclosureBody>
          <div className="border-t border-subtle px-4 pb-4 pt-2">
            {children}
          </div>
        </DisclosureBody>
      </DisclosureContent>
    </DisclosureRoot>
  );
};
