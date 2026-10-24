import { useEffect, useMemo, useState } from 'react';
import { EmptyState, Page, PageHeader, Skeleton, formatTime, inputCls, parseDate, useToast } from '../components/ui';
import type { AuditEvent, Brand } from '../types';
import { api } from '../api';

const EVENT_LABEL: Record<string, string> = {
  draft_created: 'Draft created',
  content_edited: 'Edited',
  analysis_run: 'Review run',
  correction_applied: 'Suggestion applied',
  finding_dismissed: 'Finding dismissed',
  submitted_for_review: 'Submitted',
  comment_added: 'Comment',
  changes_requested: 'Changes requested',
  content_approved: 'Approved',
  content_rejected: 'Rejected',
  content_deleted: 'Content deleted',
  rule_created: 'Rule added',
  rule_updated: 'Rule edited',
  rule_deleted: 'Rule deleted',
  claim_created: 'Claim added',
  guideline_uploaded: 'Guideline imported',
  brand_created: 'Workspace created',
  brand_updated: 'Workspace edited',
};

const EVENT_TONE: Record<string, string> = {
  content_approved: 'text-pine-700',
  content_rejected: 'text-red-700',
  changes_requested: 'text-amber-800',
  submitted_for_review: 'text-sky-800',
};

const HIDDEN_META = new Set(['comments', 'summary']);

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
        description="An append-only log of what happened in this workspace and who did it. Events are written by the server; the app has no way to edit or delete them."
        actions={
          <select value={type} onChange={(e) => setType(e.target.value)} className={`${inputCls} w-auto`} aria-label="Filter by event">
            <option value="all">All events</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {EVENT_LABEL[t] ?? t}
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
              <ol className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-white">
                {g.items.map((e) => {
                  const meta = Object.entries(e.event_metadata ?? {}).filter(([k, v]) => !HIDDEN_META.has(k) && v !== null && v !== '');
                  return (
                    <li key={e.id} className="grid gap-x-4 gap-y-1 px-4 py-3 text-[13px] sm:grid-cols-[64px_150px_minmax(0,1fr)]">
                      <span className="tabular-nums text-ink-400">{formatTime(e.created_at)}</span>
                      <span className={`font-medium ${EVENT_TONE[e.event_type] ?? 'text-ink-800'}`}>{EVENT_LABEL[e.event_type] ?? e.event_type}</span>
                      <div className="min-w-0">
                        <p className="leading-snug text-ink-800">{e.description}</p>
                        <p className="mt-1 text-[12px] text-ink-500">
                          {e.actor_name}, {e.actor_role}
                          {e.content_id && titles[e.content_id] && (
                            <>
                              {' · '}
                              <button onClick={() => navigate('studio', e.content_id)} className="underline decoration-ink-300 underline-offset-2 hover:text-ink-900">
                                {titles[e.content_id]}
                              </button>
                            </>
                          )}
                        </p>
                        {meta.length > 0 && (
                          <p className="mt-1.5 flex flex-wrap gap-1.5">
                            {meta.map(([k, v]) => (
                              <span key={k} className="rounded bg-ink-100 px-1.5 py-px font-mono text-[11px] text-ink-600" title={String(v)}>
                                {k}: {String(v).length > 40 ? `${String(v).slice(0, 40)}…` : String(v)}
                              </span>
                            ))}
                          </p>
                        )}
                      </div>
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
