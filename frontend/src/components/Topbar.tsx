import { Menu } from 'lucide-react';
import { cx } from './ui';
import type { Brand } from '../types';
import type { HealthStatus } from '../api';

const PAGE_LABEL: Record<string, string> = {
  overview: 'Overview',
  reviews: 'Content reviews',
  studio: 'Review studio',
  rulebook: 'Brand rulebook',
  approvals: 'Approval queue',
  audit: 'Audit trail',
  insights: 'Governance insights',
  settings: 'Settings',
  creative: 'Review a creative',
  sources: 'Evidence library',
  dna: 'Brand DNA',
  campaigns: 'Campaign consistency',
  governance: 'Policies & members',
  replay: 'Decision replay',
  coverage: 'Coverage map',
};

export function Topbar({ brand, page, onMenu, health }: { brand: Brand | null; page: string; onMenu: () => void; health: HealthStatus | null }) {
  const aiOn = health?.ai_engine === 'configured';
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-white px-4 sm:px-6">
      <button onClick={onMenu} className="-ml-1 rounded p-1 text-ink-500 hover:bg-ink-100 lg:hidden" aria-label="Open navigation">
        <Menu className="h-5 w-5" />
      </button>
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
        <span className="truncate text-ink-500">{brand?.name}</span>
        <span className="text-ink-300">/</span>
        <span className="truncate font-medium text-ink-900">{PAGE_LABEL[page] ?? ''}</span>
      </nav>
      <div className="ml-auto flex items-center gap-4 text-[12px] text-ink-500">
        {brand?.is_sample && <span className="hidden rounded border border-dashed border-ink-300 px-1.5 py-0.5 sm:inline">Demo data</span>}
        {health && (
          <span
            className="flex items-center gap-1.5"
            title={aiOn ? 'Rule checks plus an AI review step are enabled on the server.' : 'No AI provider key configured. Reviews use the rule engine only.'}
          >
            <span className={cx('h-1.5 w-1.5 rounded-full', aiOn ? 'bg-pine-500' : 'bg-ink-400')} />
            {aiOn ? 'Rules + AI' : 'Rules only'}
          </span>
        )}
      </div>
    </header>
  );
}
