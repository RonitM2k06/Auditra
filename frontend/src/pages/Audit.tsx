import { useEffect, useMemo, useState } from 'react';
import { Ban, BadgeCheck, BookOpen, Building2, CheckCircle2, Circle, FilePlus2, MessageSquare, Pencil, RotateCcw, ScanSearch, Send, Trash2, Upload, Wand2, XCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { EmptyState, Page, PageHeader, Skeleton, formatTime, inputCls, parseDate, useToast } from '../components/ui';
import type { AuditEvent, Brand } from '../types';
import { api } from '../api';

type Meta = Record<string, unknown>;
type EventDef = { label: string; icon: LucideIcon; tone: string; title: (m: Meta) => string };

const v = (m: Meta) => (m.version != null ? ` (v${m.version})` : '');

/** Known server event types → human-readable headline. Unknown types fall back to the server description. */
const EVENTS: Record<string, EventDef> = {
  draft_created: { label: 'Draft created', icon: FilePlus2, tone: 'text-ink-500', title: (m) => `Draft created${v(m)}` },
  content_edited: { label: 'Content edited', icon: Pencil, tone: 'text-ink-500', title: (m) => `Content edited${v(m)}` },
  analysis_run: {
    label: 'Compliance review',
    icon: ScanSearch,
    tone: 'text-sky-700',
    title: (m) => `Brand compliance review completed${v(m)}`,
  },
  correction_applied: { label: 'Correction applied', icon: Wand2, tone: 'text-pine-700', title: (m) => `Suggested correction applied${v(m)}` },
  finding_dismissed: { label: 'Finding dismissed', icon: XCircle, tone: 'text-ink-500', title: () => 'Finding dismissed' },
  submitted_for_review: { label: 'Submitted', icon: Send, tone: 'text-sky-700', title: (m) => `Content submitted for review${v(m)}` },
  comment_added: { label: 'Comment', icon: MessageSquare, tone: 'text-ink-500', title: (m) => `Comment added${v(m)}` },
  changes_requested: { label: 'Changes requested', icon: RotateCcw, tone: 'text-amber-700', title: (m) => `Changes requested by reviewer${v(m)}` },
  content_approved: { label: 'Approved', icon: CheckCircle2, tone: 'text-pine-700', title: (m) => `Content approved${v(m)}` },
  content_rejected: { label: 'Rejected', icon: Ban, tone: 'text-red-700', title: (m) => `Content rejected${v(m)}` },
  content_deleted: { label: 'Content deleted', icon: Trash2, tone: 'text-red-700', title: () => 'Content deleted' },
  rule_created: { label: 'Rule added', icon: BookOpen, tone: 'text-ink-500', title: () => 'Brand rule added' },
  rule_updated: { label: 'Rule edited', icon: BookOpen, tone: 'text-ink-500', title: () => 'Brand rule edited' },
  rule_deleted: { label: 'Rule deleted', icon: BookOpen, tone: 'text-ink-500', title: () => 'Brand rule deleted' },
  claim_created: { label: 'Claim added', icon: BadgeCheck, tone: 'text-ink-500', title: () => 'Approved claim added' },
  guideline_uploaded: { label: 'Guideline imported', icon: Upload, tone: 'text-ink-500', title: () => 'Guideline document imported' },
  brand_created: { label: 'Workspace created', icon: Building2, tone: 'text-ink-500', title: () => 'Workspace created' },
  brand_updated: { label: 'Workspace edited', icon: Building2, tone: 'text-ink-500', title: () => 'Workspace settings edited' },
};

const HIDDEN_META = new Set(['comments', 'summary']);

const FALLBACK: EventDef = { label: 'Event', icon: Circle, tone: 'text-ink-400', title: () => '' };

const ENGINE_LABEL: Record<string, string> = { deterministic: 'Rule engine', hybrid_ai: 'Rules + AI' };
const STATUS_WORD: Record<string, string> = {
  draft: 'Draft',
  in_review: 'In review',
  changes_requested: 'Changes requested',
  approved: 'Approved',
  rejected: 'Rejected',
};

/** Metadata shown as labelled fields; everything else (ids, raw payloads) stays in "Details". */
function fieldsFor(m: Meta): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  if (m.findings_count != null) out.push(['Findings', String(m.findings_count)]);
  if (typeof m.engine === 'string') out.push(['Method', ENGINE_LABEL[m.engine] ?? m.engine]);
  if (typeof m.from === 'string') out.push(['Replaced', `“${m.from}”`]);
  if (typeof m.to === 'string') out.push(['With', `“${m.to}”`]);
  if (typeof m.previous_status === 'string') out.push(['Previous status', STATUS_WORD[m.previous_status] ?? m.previous_status]);
  return out;
}

/** Reviewer decisions carry the note in the server description ("… Note: <text>"). */
const noteOf = (description: string) => description.match(/Note:\s*(.+)$/s)?.[1]?.trim();

export function Audit({ brand, navigate }: { brand: Brand; navigate: (page: string, id?: string | null) => void }) {
  const toast = useToast();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [titles, setTitles] = useState<Record<string, string>>({});
  const [type, setType] = useState('all');

  useEffect(() => {
    setEvents(null);
    Promise.all([api.getAuditTrail(brand.id), api.getContentItems(brand.id)])
      .then(([ev, items]) => {
        setEvents(ev);
        setTitles(Object.fromEntries(items.map((i) => [i.id, i.title])));
      })
      .catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  const types = useMemo(() => Array.from(new Set((events ?? []).map((e) => e.event_type))), [events]);
  const groups = useMemo(() => {
    const out: Array<{ day: string; items: AuditEvent[] }> = [];
    for (const e of events ?? []) {
      if (type !== 'all' && e.event_type !== type) continue;
      const day = parseDate(e.created_at).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
      const last = out[out.length - 1];
      if (last?.day === day) last.items.push(e);
      else out.push({ day, items: [e] });
    }
    return out;
  }, [events, type]);

  return (
    <Page width="max-w-5xl">
      <PageHeader
        title="Audit trail"
        description="What changed, who acted, and how each decision was reached. Events are recorded by the server as they happen."
        actions={
          <select value={type} onChange={(e) => setType(e.target.value)} className={`${inputCls} w-auto`} aria-label="Filter by event">
            <option value="all">All events</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {EVENTS[t]?.label ?? t.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        }
      />

      {events === null ? (
        <Skeleton className="h-96 w-full" />
      ) : groups.length === 0 ? (
        <EmptyState title="No events" body="Actions like saving, reviewing, and approving content are recorded here." />
      ) : (
        <div className="space-y-8">
          {groups.map((g) => (
            <section key={g.day}>
              <h2 className="mb-2 text-[12.5px] font-medium text-ink-500">{g.day}</h2>
              <ol className="rounded-lg border border-line bg-white px-4 py-5 sm:px-6">
                {g.items.map((e) => {
                  const m = (e.event_metadata ?? {}) as Meta;
                  const def = EVENTS[e.event_type] ?? FALLBACK;
                  const Icon = def.icon;
                  const fields = fieldsFor(m);
                  const note = ['changes_requested', 'content_approved', 'content_rejected', 'comment_added'].includes(e.event_type) ? noteOf(e.description) : undefined;
                  return (
                    <li key={e.id} className="relative pb-6 pl-10 last:pb-0">
                      <span className="absolute left-[15px] top-8 bottom-0 w-px bg-line" aria-hidden />
                      <span className={`absolute left-0 top-0.5 grid h-8 w-8 place-items-center rounded-full border border-line bg-white ${def.tone}`}>
                        <Icon className="h-4 w-4" aria-hidden />
                      </span>
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                        <p className="text-[14px] font-medium text-ink-900">{def.title(m) || e.description}</p>
                        <time dateTime={e.created_at} className="text-[12px] tabular-nums text-ink-400">
                          {formatTime(e.created_at)}
                        </time>
                      </div>
                      <p className="mt-0.5 text-[12.5px] text-ink-500">
                        {e.actor_name}
                        {e.actor_role && <span className="text-ink-400"> · {e.actor_role}</span>}
                        {e.content_id && titles[e.content_id] && (
                          <>
                            {' · '}
                            <button onClick={() => navigate('studio', e.content_id)} className="text-left font-medium text-ink-700 underline decoration-ink-300 underline-offset-2 hover:text-ink-900">
                              {titles[e.content_id]}
                            </button>
                          </>
                        )}
                      </p>
                      {note && <blockquote className="mt-2 border-l-2 border-ink-200 pl-3 text-[13px] leading-relaxed text-ink-700">{note}</blockquote>}
                      {fields.length > 0 && (
                        <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px]">
                          {fields.map(([k, val]) => (
                            <div key={k} className="flex min-w-0 gap-1.5">
                              <dt className="text-ink-400">{k}</dt>
                              <dd className="min-w-0 truncate text-ink-700" title={val}>{val}</dd>
                            </div>
                          ))}
                        </dl>
                      )}
                      <details className="group mt-1.5 text-[12px]">
                        <summary className="cursor-pointer select-none text-ink-400 hover:text-ink-700">Details</summary>
                        <div className="mt-1.5 space-y-1 rounded-md bg-ink-50 px-3 py-2 text-ink-600">
                          <p>{e.description}</p>
                          <p className="text-ink-400">
                            Event type <code className="font-mono">{e.event_type}</code> · {parseDate(e.created_at).toLocaleString()}
                          </p>
                          {Object.entries(m)
                            .filter(([k, val]) => !HIDDEN_META.has(k) && val !== null && val !== '')
                            .map(([k, val]) => (
                              <p key={k} className="break-all font-mono text-[11px] text-ink-500">
                                {k}: {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                              </p>
                            ))}
                        </div>
                      </details>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
    </Page>
  );
}
