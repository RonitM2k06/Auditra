import { useEffect, useRef, useState } from 'react';
import { BarChart2, BookOpen, Check, ChevronsUpDown, Dna, FilePlus2, FileSearch, FileText, History, ImageUp, Inbox, LayoutGrid, LogOut, Network, Plus, Settings, ShieldCheck, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cx, Logo, ROLE_LABEL, type Role } from './ui';
import type { Brand, Me } from '../types';

type NavEntry = { id: string; label: string; icon: LucideIcon; showCount?: boolean };

const NAV: Array<{ group: string; items: NavEntry[] }> = [
  {
    group: 'Workspace',
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutGrid },
      { id: 'reviews', label: 'Content reviews', icon: FileText },
      { id: 'studio', label: 'New copy review', icon: FilePlus2 },
      { id: 'creative', label: 'Review a creative', icon: ImageUp },
      { id: 'campaigns', label: 'Campaigns', icon: Network },
    ],
  },
  {
    group: 'Brand governance',
    items: [
      { id: 'approvals', label: 'Approval queue', icon: Inbox, showCount: true },
      { id: 'rulebook', label: 'Brand rulebook', icon: BookOpen },
      { id: 'sources', label: 'Evidence library', icon: FileSearch },
      { id: 'dna', label: 'Brand DNA', icon: Dna },
      { id: 'audit', label: 'Audit trail', icon: History },
    ],
  },
  { group: 'Insights', items: [{ id: 'insights', label: 'Governance insights', icon: BarChart2 }] },
  {
    group: 'Configuration',
    items: [
      { id: 'governance', label: 'Policies & members', icon: ShieldCheck },
      { id: 'settings', label: 'Settings', icon: Settings },
    ],
  },
];

interface SidebarProps {
  page: string;
  navigate: (page: string, id?: string | null) => void;
  brands: Brand[];
  brand: Brand | null;
  onSelectBrand: (b: Brand) => void;
  onNewBrand: () => void;
  role: Role;
  me: Me;
  onSignOut: () => void;
  queueCount: number;
  open: boolean;
  onClose: () => void;
  hasId: boolean;
}

export function Sidebar({ page, navigate, brands, brand, onSelectBrand, onNewBrand, role, me, onSignOut, queueCount, open, onClose, hasId }: SidebarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  // An existing review highlights "Content reviews"; a blank studio highlights "New review".
  const active = page === 'studio' || page === 'replay' ? (hasId ? 'reviews' : 'studio') : page;

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [menuOpen]);

  const item = (n: NavEntry) => {
    const Icon = n.icon;
    const isActive = active === n.id;
    return (
      <button
        key={n.id}
        onClick={() => navigate(n.id)}
        aria-current={isActive ? 'page' : undefined}
        className={cx(
          'relative flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-[13.5px] transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine-500/70',
          isActive ? 'bg-pine-500/[0.14] font-medium text-white' : 'text-slate-300 hover:bg-white/[0.06] hover:text-white',
        )}
      >
        {isActive && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r bg-pine-500" aria-hidden />}
        <Icon className={cx('h-[18px] w-[18px]', isActive ? 'text-teal-300' : 'text-slate-400')} strokeWidth={1.75} />
        <span className="flex-1 text-left">{n.label}</span>
        {n.showCount && queueCount > 0 && (
          <span className="min-w-[20px] rounded-full bg-pine-500 px-1.5 text-center text-[11px] font-semibold leading-[18px] text-white">{queueCount}</span>
        )}
      </button>
    );
  };

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-navy-950/50 lg:hidden" onClick={onClose} aria-hidden />}
      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-[248px] shrink-0 flex-col bg-navy-900 transition-transform duration-200 lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center justify-between px-4">
          <Logo dark />
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white lg:hidden" aria-label="Close navigation">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace switcher */}
        <div className="relative px-3" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="listbox"
            aria-expanded={menuOpen}
            className="flex w-full items-center gap-2.5 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-2 text-left transition-colors hover:bg-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine-500/70"
          >
            <span
              className="grid h-6 w-6 shrink-0 place-items-center rounded text-[12px] font-semibold text-white"
              style={{ backgroundColor: brand?.secondary_color || '#1b1a18' }}
            >
              {brand?.name.charAt(0) ?? '?'}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-white">{brand?.name ?? 'No workspace'}</span>
              <span className="block truncate text-[11.5px] text-slate-400">{brand?.is_sample ? 'Demo workspace' : brand?.industry}</span>
            </span>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          </button>

          {menuOpen && (
            <div role="listbox" className="absolute left-3 right-3 top-full z-50 mt-1 rounded-md border border-line bg-white py-1 shadow-lg shadow-ink-900/5">
              <p className="px-3 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wider text-ink-400">Workspaces</p>
              {brands.map((b) => (
                <button
                  key={b.id}
                  role="option"
                  aria-selected={b.id === brand?.id}
                  onClick={() => {
                    onSelectBrand(b);
                    setMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] text-ink-800 hover:bg-ink-50"
                >
                  <span className="flex-1 truncate">{b.name}</span>
                  {b.is_sample && <span className="text-[11px] text-ink-400">demo</span>}
                  {b.id === brand?.id && <Check className="h-3.5 w-3.5 text-ink-900" />}
                </button>
              ))}
              <div className="mt-1 border-t border-line pt-1">
                <button
                  onClick={() => {
                    setMenuOpen(false);
                    onNewBrand();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] text-ink-600 hover:bg-ink-50 hover:text-ink-900"
                >
                  <Plus className="h-3.5 w-3.5" /> New workspace
                </button>
              </div>
            </div>
          )}
        </div>

        <nav className="mt-4 flex-1 space-y-5 overflow-y-auto px-3" aria-label="Main">
          {NAV.map((g, i) => (
            <div key={i}>
              <p className="mb-1.5 px-2.5 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-slate-500">{g.group}</p>
              <div className="space-y-px">{g.items.map(item)}</div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-pine-600 text-[12px] font-semibold text-white">
              {me.display_name.split(' ').map((w) => w[0]).slice(0, 2).join('')}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-white">{me.display_name}</span>
              <span className="block truncate text-[11.5px] text-slate-400">{ROLE_LABEL[role]}{me.is_demo ? ' · demo' : ''}</span>
            </span>
            <button onClick={onSignOut} className="rounded p-1.5 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Sign out" title="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-2 text-[11px] leading-snug text-slate-500">Permissions for this role are enforced by the server on every request.</p>
        </div>
      </aside>
    </>
  );
}
