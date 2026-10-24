import { useEffect, useRef, useState } from 'react';
import { BarChart2, BookOpen, Check, ChevronsUpDown, FileText, History, Inbox, LayoutGrid, Plus, Settings, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { ACTORS, Button, cx, Logo, type Role } from './ui';
import type { Brand } from '../types';

type NavEntry = { id: string; label: string; icon: LucideIcon; showCount?: boolean };

const NAV: Array<{ group: string | null; items: NavEntry[] }> = [
  {
    group: null,
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutGrid },
      { id: 'reviews', label: 'Content reviews', icon: FileText },
      { id: 'approvals', label: 'Approval queue', icon: Inbox, showCount: true },
    ],
  },
  { group: 'Policy', items: [{ id: 'rulebook', label: 'Brand rulebook', icon: BookOpen }] },
  {
    group: 'Records',
    items: [
      { id: 'audit', label: 'Audit trail', icon: History },
      { id: 'insights', label: 'Insights', icon: BarChart2 },
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
  setRole: (r: Role) => void;
  queueCount: number;
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ page, navigate, brands, brand, onSelectBrand, onNewBrand, role, setRole, queueCount, open, onClose }: SidebarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const active = page === 'studio' ? 'reviews' : page;

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
          'flex w-full items-center gap-2.5 rounded-md px-2 py-[7px] text-[13.5px] transition-colors',
          isActive ? 'bg-white font-medium text-ink-900 ring-1 ring-line' : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
        )}
      >
        <Icon className={cx('h-4 w-4', isActive ? 'text-ink-900' : 'text-ink-400')} strokeWidth={1.75} />
        <span className="flex-1 text-left">{n.label}</span>
        {n.showCount && queueCount > 0 && (
          <span className="min-w-[20px] rounded-full bg-ink-900 px-1.5 text-center text-[11px] font-medium leading-[18px] text-white">{queueCount}</span>
        )}
      </button>
    );
  };

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-ink-900/20 lg:hidden" onClick={onClose} aria-hidden />}
      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-[244px] shrink-0 flex-col border-r border-line bg-ink-50 transition-transform duration-200 lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-12 items-center justify-between px-4">
          <Logo />
          <button onClick={onClose} className="rounded p-1 text-ink-500 hover:bg-ink-100 lg:hidden" aria-label="Close navigation">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace switcher */}
        <div className="relative px-3" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-haspopup="listbox"
            aria-expanded={menuOpen}
            className="flex w-full items-center gap-2.5 rounded-md border border-line bg-white px-2 py-1.5 text-left hover:border-ink-300"
          >
            <span
              className="grid h-6 w-6 shrink-0 place-items-center rounded text-[12px] font-semibold text-white"
              style={{ backgroundColor: brand?.secondary_color || '#1b1a18' }}
            >
              {brand?.name.charAt(0) ?? '?'}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-ink-900">{brand?.name ?? 'No workspace'}</span>
              <span className="block truncate text-[11.5px] text-ink-500">{brand?.is_sample ? 'Demo workspace' : brand?.industry}</span>
            </span>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-ink-400" />
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

        <div className="px-3 pt-3">
          <Button variant="primary" className="w-full" onClick={() => navigate('studio')}>
            <Plus className="h-3.5 w-3.5" /> New review
          </Button>
        </div>

        <nav className="mt-5 flex-1 space-y-5 overflow-y-auto px-2" aria-label="Main">
          {NAV.map((g, i) => (
            <div key={i}>
              {g.group && <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-ink-400">{g.group}</p>}
              <div className="space-y-px">{g.items.map(item)}</div>
            </div>
          ))}
        </nav>

        <div className="px-2 pb-2">{item({ id: 'settings', label: 'Settings', icon: Settings })}</div>

        <div className="border-t border-line p-3">
          <label htmlFor="role-select" className="block text-[11px] font-medium uppercase tracking-wider text-ink-400">
            Acting as
          </label>
          <select
            id="role-select"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="mt-1.5 w-full rounded-md border border-line bg-white px-2 py-1.5 text-[13px] text-ink-900 focus:border-ink-400 focus:outline-none"
          >
            {(Object.keys(ACTORS) as Role[]).map((r) => (
              <option key={r} value={r}>
                {ACTORS[r].name} · {ACTORS[r].role}
              </option>
            ))}
          </select>
          <p className="mt-1.5 text-[11.5px] leading-snug text-ink-400">Demo roles for evaluation. There is no login, so this is not access control.</p>
        </div>
      </aside>
    </>
  );
}
