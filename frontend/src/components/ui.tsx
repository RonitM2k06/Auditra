/**
 * Shared UI primitives and display metadata for Auditra.
 * Everything visual that is reused across pages lives here so the system stays consistent.
 */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';

export const cx = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ */
/* Domain display metadata                                             */
/* ------------------------------------------------------------------ */

export type Role = 'creator' | 'reviewer' | 'admin';

export const ACTORS: Record<Role, { name: string; role: string }> = {
  creator: { name: 'Alex Rivers', role: 'Content Creator' },
  reviewer: { name: 'Sarah Chen', role: 'Brand Compliance Lead' },
  admin: { name: 'Workspace Admin', role: 'Administrator' },
};

export const STATUS_META: Record<string, { label: string; dot: string; text: string }> = {
  draft: { label: 'Draft', dot: 'bg-ink-400', text: 'text-ink-600' },
  in_review: { label: 'In review', dot: 'bg-sky-600', text: 'text-sky-800' },
  changes_requested: { label: 'Changes requested', dot: 'bg-amber-500', text: 'text-amber-800' },
  approved: { label: 'Approved', dot: 'bg-pine-500', text: 'text-pine-700' },
  rejected: { label: 'Rejected', dot: 'bg-red-600', text: 'text-red-700' },
};

export const SEV_META: Record<string, { label: string; text: string; bg: string; bar: string; mark: string }> = {
  critical: { label: 'Critical', text: 'text-red-700', bg: 'bg-red-50', bar: 'bg-red-600', mark: 'bg-red-100/70 decoration-red-500' },
  high: { label: 'High', text: 'text-amber-800', bg: 'bg-amber-50', bar: 'bg-amber-500', mark: 'bg-amber-100/70 decoration-amber-500' },
  medium: { label: 'Medium', text: 'text-sky-800', bg: 'bg-sky-50', bar: 'bg-sky-600', mark: 'bg-sky-100/70 decoration-sky-500' },
  low: { label: 'Low', text: 'text-ink-600', bg: 'bg-ink-100', bar: 'bg-ink-400', mark: 'bg-ink-100 decoration-ink-400' },
};

export const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const;

export const CATEGORY_LABEL: Record<string, string> = {
  prohibited_term: 'Prohibited wording',
  preferred_term: 'Terminology',
  required_phrase: 'Required disclosure',
  restricted_claim: 'Restricted claim',
  unverified_claim: 'Unverified claim',
  approved_claim: 'Approved claim',
  tone_voice: 'Tone & voice',
  formatting_style: 'Style',
};

export const CONTENT_TYPES: Record<string, string> = {
  social_post: 'Social post',
  advertisement: 'Advertisement',
  email: 'Email',
  landing_page: 'Landing page',
  announcement: 'Announcement',
  blog_post: 'Blog / case study',
};

/* ------------------------------------------------------------------ */
/* Dates                                                               */
/* ------------------------------------------------------------------ */

/** The API stores UTC timestamps; SQLite may drop the zone, so treat naive values as UTC. */
export function parseDate(iso: string): Date {
  return new Date(/Z$|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function timeAgo(iso: string): string {
  const seconds = Math.round((Date.now() - parseDate(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return parseDate(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatDateTime(iso: string): string {
  return parseDate(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatTime(iso: string): string {
  return parseDate(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

/* ------------------------------------------------------------------ */
/* Primitives                                                          */
/* ------------------------------------------------------------------ */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'dangerSolid' | 'accent';

export const Button = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: 'sm' | 'md' }
>(({ variant = 'secondary', size = 'md', className, type = 'button', ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    {...props}
    className={cx(
      'inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink-900/20 focus-visible:ring-offset-1',
      'disabled:pointer-events-none disabled:opacity-50',
      size === 'sm' ? 'h-7 px-2.5 text-[12.5px]' : 'h-8 px-3 text-[13px]',
      variant === 'primary' && 'bg-ink-900 text-white hover:bg-ink-700',
      variant === 'secondary' && 'border border-line bg-white text-ink-800 hover:border-ink-300 hover:bg-ink-50',
      variant === 'ghost' && 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
      variant === 'danger' && 'border border-line bg-white text-red-700 hover:border-red-200 hover:bg-red-50',
      variant === 'dangerSolid' && 'bg-red-700 text-white hover:bg-red-800',
      variant === 'accent' && 'bg-pine-600 text-white hover:bg-pine-700',
      className,
    )}
  />
));
Button.displayName = 'Button';

export function StatusPill({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.draft;
  return (
    <span className={cx('inline-flex items-center gap-1.5 whitespace-nowrap text-[12.5px] font-medium', meta.text)}>
      <span className={cx('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {meta.label}
    </span>
  );
}

export function SeverityTag({ severity }: { severity: string }) {
  const meta = SEV_META[severity] ?? SEV_META.low;
  return (
    <span className={cx('inline-flex items-center rounded px-1.5 py-px text-[11px] font-semibold uppercase tracking-wide', meta.bg, meta.text)}>
      {meta.label}
    </span>
  );
}

export function Page({ children, width = 'max-w-6xl' }: { children: React.ReactNode; width?: string }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className={cx('mx-auto space-y-8 px-5 py-7 sm:px-8', width)}>{children}</div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="font-serif text-[28px] leading-tight tracking-tight text-ink-900">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-[13.5px] leading-relaxed text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Section({ title, description, action, children }: { title: string; description?: React.ReactNode; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-[13.5px] font-semibold text-ink-900">{title}</h2>
          {description && <p className="mt-0.5 text-[12.5px] text-ink-500">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function EmptyState({ title, body, action }: { title: string; body?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-ink-300 px-6 py-10 text-center">
      <p className="text-[14px] font-medium text-ink-800">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-sm text-[13px] text-ink-500">{body}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded bg-ink-100', className)} />;
}

export function PageSkeleton() {
  return (
    <Page>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-20 w-full" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-64 lg:col-span-2" />
        <Skeleton className="h-64" />
      </div>
    </Page>
  );
}

export const inputCls =
  'w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-[13.5px] text-ink-900 placeholder:text-ink-400 ' +
  'focus:border-ink-400 focus:outline-none focus:ring-2 focus:ring-ink-900/5 disabled:bg-ink-50';

export function Field({ label, hint, required, children }: { label: string; hint?: React.ReactNode; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12.5px] font-medium text-ink-700">
        {label}
        {required && <span className="text-red-600"> *</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[12px] text-ink-400">{hint}</span>}
    </label>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
      className={cx(
        'relative inline-flex h-[18px] w-8 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink-900/20',
        checked ? 'bg-pine-500' : 'bg-ink-300',
      )}
    >
      <span className={cx('inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform', checked ? 'translate-x-[16px]' : 'translate-x-[2px]')} />
    </button>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: Array<{ id: T; label: string; count?: number }> }) {
  return (
    <div className="flex gap-5 overflow-x-auto border-b border-line" role="tablist">
      {items.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            '-mb-px whitespace-nowrap border-b-2 pb-2 text-[13px] transition-colors',
            value === t.id ? 'border-ink-900 font-medium text-ink-900' : 'border-transparent text-ink-500 hover:text-ink-800',
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 text-ink-400">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <span className="grid h-6 w-6 place-items-center rounded-[6px] bg-ink-900 pb-0.5 font-serif text-[16px] italic leading-none text-white">a</span>
      <span className="font-serif text-[19px] tracking-tight text-ink-900">Auditra</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Modal                                                               */
/* ------------------------------------------------------------------ */

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = 'max-w-lg',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink-900/30 p-4 pt-[8vh]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div role="dialog" aria-modal="true" aria-label={title} className={cx('w-full rounded-lg border border-line bg-white shadow-2xl shadow-ink-900/10', width)}>
        <div className="flex items-start justify-between gap-4 px-5 pb-3 pt-4">
          <div>
            <h2 className="text-[15px] font-semibold text-ink-900">{title}</h2>
            {description && <p className="mt-1 text-[13px] leading-relaxed text-ink-500">{description}</p>}
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700">
            <X className="h-4 w-4" />
          </button>
        </div>
        {children && <div className="px-5 pb-4">{children}</div>}
        {footer && <div className="flex justify-end gap-2 rounded-b-lg border-t border-line bg-ink-50/70 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Confirm dialog                                                      */
/* ------------------------------------------------------------------ */

type ConfirmOptions = { title: string; body?: React.ReactNode; confirmLabel?: string; danger?: boolean };
const ConfirmContext = createContext<(o: ConfirmOptions) => Promise<boolean>>(async () => false);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<(ConfirmOptions & { resolve: (v: boolean) => void }) | null>(null);
  const confirm = useCallback((o: ConfirmOptions) => new Promise<boolean>((resolve) => setState({ ...o, resolve })), []);
  const close = useCallback(
    (value: boolean) => {
      setState((s) => {
        s?.resolve(value);
        return null;
      });
    },
    [],
  );

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal
        open={!!state}
        onClose={() => close(false)}
        title={state?.title ?? ''}
        description={state?.body}
        width="max-w-md"
        footer={
          <>
            <Button onClick={() => close(false)}>Cancel</Button>
            <Button variant={state?.danger ? 'dangerSolid' : 'primary'} onClick={() => close(true)} autoFocus>
              {state?.confirmLabel ?? 'Confirm'}
            </Button>
          </>
        }
      />
    </ConfirmContext.Provider>
  );
}

export const useConfirm = () => useContext(ConfirmContext);

/* ------------------------------------------------------------------ */
/* Toasts                                                              */
/* ------------------------------------------------------------------ */

type Tone = 'success' | 'error' | 'info';
type ToastItem = { id: number; text: string; tone: Tone };
const ToastContext = createContext<(text: string, tone?: Tone) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const push = useCallback((text: string, tone: Tone = 'info') => {
    const id = ++nextId.current;
    setItems((prev) => [...prev.slice(-2), { id, text, tone }]);
    window.setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), tone === 'error' ? 7000 : 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-5 left-1/2 z-[60] flex w-full max-w-md -translate-x-1/2 flex-col items-center gap-2 px-4">
        {items.map((t) => (
          <div key={t.id} className="pointer-events-auto flex w-full items-start gap-2.5 rounded-md bg-ink-900 px-3.5 py-2.5 text-[13px] text-white shadow-lg">
            <span className={cx('mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full', t.tone === 'success' ? 'bg-pine-200' : t.tone === 'error' ? 'bg-red-400' : 'bg-ink-400')} />
            <span className="flex-1 leading-relaxed">{t.text}</span>
            <button onClick={() => setItems((p) => p.filter((x) => x.id !== t.id))} className="mt-0.5 text-ink-400 hover:text-white" aria-label="Dismiss">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
