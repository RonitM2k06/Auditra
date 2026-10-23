import React from 'react';
import { Sparkles, Shield, User } from 'lucide-react';
import { Brand } from '../types';

interface NavbarProps {
  currentTab: string;
  selectedBrand: Brand | null;
  userRole: 'creator' | 'reviewer' | 'admin';
  onNewReviewClick: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  selectedBrand,
  userRole,
  onNewReviewClick,
}) => {
  const tabTitles: Record<string, { title: string; desc: string }> = {
    overview: {
      title: 'Command Centre',
      desc: 'Real-time brand compliance health, high-risk items, and governance throughput.',
    },
    reviews: {
      title: 'Content Reviews',
      desc: 'All drafts, queued reviews, and approved assets across omni-channel campaigns.',
    },
    studio: {
      title: 'Review Studio',
      desc: 'Interactive compliance editor with deterministic rule detection and one-click corrections.',
    },
    rulebook: {
      title: 'Brand Rulebook & Claims Registry',
      desc: 'Active terminology guardrails, prohibited phrases, required disclosures, and verified facts.',
    },
    approvals: {
      title: 'Governance Approval Queue',
      desc: 'Pending reviews requiring formal human compliance decisions and editorial feedback.',
    },
    audit: {
      title: 'Audit Trail & Event Log',
      desc: 'Chronological immutable event history tracking all drafts, scans, edits, and decisions.',
    },
    insights: {
      title: 'Governance Insights & Analytics',
      desc: 'Violation patterns, recurring editorial friction, and rule clarity recommendations.',
    },
    settings: {
      title: 'Governance Settings',
      desc: 'Brand profile, AI engine preferences, and demonstration data maintenance.',
    },
  };

  const currentInfo = tabTitles[currentTab] || { title: 'AUDITRA', desc: 'Brand Governance' };

  return (
    <header className="h-16 bg-white border-b border-surface-border px-6 flex items-center justify-between shrink-0 z-10">
      <div>
        <h1 className="text-lg font-bold text-dark-primary flex items-center gap-2">
          {currentInfo.title}
          {selectedBrand && (
            <span className="text-xs font-normal text-dark-muted px-2 py-0.5 bg-surface-muted rounded-full border border-surface-border">
              {selectedBrand.name}
            </span>
          )}
        </h1>
        <p className="text-xs text-dark-muted hidden md:block">{currentInfo.desc}</p>
      </div>

      <div className="flex items-center gap-3">
        {currentTab !== 'studio' && (
          <button
            onClick={onNewReviewClick}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>New Review</span>
          </button>
        )}

        <div className="flex items-center gap-2 pl-3 border-l border-surface-border">
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-muted rounded-lg text-xs font-medium text-dark-secondary">
            <Shield className="w-3.5 h-3.5 text-brand-500" />
            <span className="capitalize">{userRole}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
