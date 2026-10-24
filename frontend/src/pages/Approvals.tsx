import React, { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, Inbox } from 'lucide-react';
import {
  ACTORS,
  Button,
  CATEGORY_LABEL,
  CONTENT_TYPES,
  EmptyState,
  Page,
  PageHeader,
  SeverityTag,
  SEVERITIES,
  Skeleton,
  cx,
  inputCls,
  timeAgo,
  useToast,
  type Role,
} from '../components/ui';
import { DecisionModal, type Decision } from '../components/DecisionModal';
import type { Brand, ContentItemDetail, Finding } from '../types';
import { api } from '../api';

interface ApprovalsProps {
  brand: Brand;
  role: Role;
  navigate: (page: string, id?: string | null) => void;
  onChanged: () => void;
}

/** Open findings on the reviewed current version, or null when the current version has no review. */
function openFindings(i: ContentItemDetail): Finding[] | null {
  const r = i.latest_review;
  if (!r || r.content_version_id !== i.current_version?.id) return null;
  return r.findings.filter((f) => !f.is_applied && !f.is_dismissed);
}

const highest = (fs: Finding[]) => SEVERITIES.find((s) => fs.some((f) => f.severity === s));

export function Approvals({ brand, role, navigate, onChanged }: ApprovalsProps) {
  const toast = useToast();
  const actor = ACTORS[role];
  const canDecide = role !== 'creator';
  const [items, setItems] = useState<ContentItemDetail[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState('');
  const [counts, setCounts] = useState<Record<string, number> | null>(null);

  const load = useCallback(async () => {
    try {
      const [list, all] = await Promise.all([api.getContentItems(brand.id, 'in_review'), api.getContentItems(brand.id)]);
      setCounts(all.reduce<Record<string, number>>((acc, i) => ({ ...acc, [i.status]: (acc[i.status] ?? 0) + 1 }), {}));
      const detailed = await Promise.all(list.map((i) => api.getContentItem(i.id)));
      setItems(detailed);
      setSelectedId((cur) => (cur && detailed.some((d) => d.id === cur) ? cur : detailed[0]?.id ?? null));
    } catch (e: any) {
      toast(e.message, 'error');
    }
  }, [brand.id, toast]);

  useEffect(() => {
    setItems(null);
    load();
  }, [load]);

  const selected = items?.find((i) => i.id === selectedId) ?? null;
  const review = selected?.latest_review;
  const reviewCurrent = !!review && review.content_version_id === selected?.current_version?.id;
  const open = reviewCurrent ? review!.findings.filter((f) => !f.is_applied && !f.is_dismissed) : [];
  const serious = open.filter((f) => f.severity === 'critical' || f.severity === 'high').length;

  const decide = async (note: string) => {
    if (!selected || !decision) return;
    setBusy(true);
    try {
      await api.recordDecision(selected.id, { decision, reviewer_name: actor.name, reviewer_role: actor.role, comments: note || undefined });
      toast(`${selected.title}: ${decision === 'approved' ? 'approved' : decision === 'rejected' ? 'rejected' : 'changes requested'}.`, 'success');
      setDecision(null);
      await load();
      onChanged();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const postComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !comment.trim()) return;
    try {
      await api.addComment(selected.id, { text: comment.trim(), author_name: actor.name, author_role: actor.role });
      const fresh = await api.getContentItem(selected.id);
      setItems((list) => list?.map((i) => (i.id === fresh.id ? fresh : i)) ?? null);
      setComment('');
    } catch (err: any) {
      toast(err.message, 'error');
    }
  };

  return (
    <Page width="max-w-7xl">
      <PageHeader
        title="Approval queue"
        description="Review submitted content and make accountable decisions. Automated findings inform the decision; they never make it."
      />

      {counts && (
        <dl className="grid grid-cols-2 overflow-hidden rounded-lg border border-line bg-white sm:grid-cols-4">
          {[
            ['Awaiting review', counts.in_review ?? 0, 'text-sky-700'],
            ['Changes requested', counts.changes_requested ?? 0, 'text-amber-700'],
            ['Approved', counts.approved ?? 0, 'text-pine-700'],
            ['Rejected', counts.rejected ?? 0, 'text-red-700'],
          ].map(([label, n, tone], i) => (
            <div key={label as string} className={cx('px-5 py-3.5', i % 2 === 1 && 'border-l border-line', i >= 2 && 'border-t border-line sm:border-t-0', i === 2 && 'sm:border-l')}>
              <dt className="text-[12.5px] text-ink-500">{label}</dt>
              <dd className={cx('mt-1 text-[22px] font-semibold leading-none tabular-nums', n ? (tone as string) : 'text-ink-300')}>{n}</dd>
            </div>
          ))}
        </dl>
      )}

      {items === null ? (
        <Skeleton className="h-96 w-full" />
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-line bg-white px-6 py-14 text-center">
          <span className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-pine-50 text-pine-700">
            <Inbox className="h-5 w-5" aria-hidden />
          </span>
          <p className="mt-3 text-[15px] font-medium text-ink-900">No content is awaiting review</p>
          <p className="mx-auto mt-1 max-w-sm text-[13px] leading-relaxed text-ink-500">
            When a creator submits a piece for approval, it appears here with its findings and discussion.
          </p>
          <div className="mt-5 flex justify-center gap-2">
            <Button onClick={() => navigate('overview')}>Go to overview</Button>
            <Button variant="primary" onClick={() => navigate('reviews')}>
              View content reviews
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <div>
          <p className="mb-2 text-[12px] font-medium text-ink-500">
            {items.length} awaiting decision · oldest first
          </p>
          <ul className="space-y-1.5">
            {[...items].sort((a, b) => a.updated_at.localeCompare(b.updated_at)).map((i) => {
              const fs = openFindings(i);
              const top = fs && highest(fs);
              return (
              <li key={i.id}>
                <button
                  onClick={() => setSelectedId(i.id)}
                  className={cx(
                    'w-full rounded-md border px-3 py-2.5 text-left transition-colors',
                    i.id === selectedId ? 'border-pine-600 bg-white ring-1 ring-pine-600' : 'border-line bg-white hover:border-ink-300',
                  )}
                >
                  <p className="truncate text-[13.5px] font-medium text-ink-900">{i.title}</p>
                  <p className="mt-0.5 text-[12px] text-ink-500">
                    {i.created_by} · v{i.current_version_number} · submitted {timeAgo(i.updated_at)}
                  </p>
                  <p className="mt-2 flex items-center gap-2 text-[12px] text-ink-600">
                    {fs === null ? (
                      <span className="text-amber-800">Not reviewed on this version</span>
                    ) : fs.length === 0 ? (
                      <span className="text-pine-700">No open findings</span>
                    ) : (
                      <>
                        {top && <SeverityTag severity={top} />}
                        <span>
                          {fs.length} open finding{fs.length === 1 ? '' : 's'}
                        </span>
                      </>
                    )}
                  </p>
                </button>
              </li>
              );
            })}
          </ul>
          </div>

          {selected && (
            <div className="min-w-0 rounded-lg border border-line bg-white">
              <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h2 className="text-[16px] font-semibold text-ink-900">{selected.title}</h2>
                  <p className="mt-0.5 text-[12.5px] text-ink-500">
                    {CONTENT_TYPES[selected.content_type]} · by {selected.created_by} · version {selected.current_version_number}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="ghost" onClick={() => navigate('studio', selected.id)}>
                    Open in studio <ArrowUpRight className="h-3 w-3" />
                  </Button>
                  {canDecide && (
                    <>
                      <Button size="sm" onClick={() => setDecision('changes_requested')}>
                        Request changes
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => setDecision('rejected')}>
                        Reject
                      </Button>
                      <Button size="sm" variant="accent" onClick={() => setDecision('approved')}>
                        Approve
                      </Button>
                    </>
                  )}
                </div>
              </div>

              <div className={cx('border-b border-line px-5 py-3 text-[13px] leading-relaxed', serious > 0 || !reviewCurrent ? 'bg-amber-50 text-amber-900' : 'bg-pine-50 text-pine-700')}>
                <p>
                  <span className="font-medium">Why this needs review: </span>
                  {selected.created_by} submitted version {selected.current_version_number} {timeAgo(selected.updated_at)}.{' '}
                  {!reviewCurrent
                    ? 'This version has no current automated review.'
                    : open.length === 0
                      ? 'Automated checks found no open issues.'
                      : `${open.length} finding${open.length === 1 ? ' is' : 's are'} still open${serious > 0 ? `, ${serious} critical or high` : ''}.`}
                </p>
                <p className="mt-0.5">
                  <span className="font-medium">Next step: </span>
                  {canDecide
                    ? 'Read the copy and findings, then approve, request changes, or reject. A note is required to send it back or reject it.'
                    : `You're acting as ${actor.name}, a creator, so you can comment but not decide. Switch to the reviewer under "Acting as" in the sidebar to record a decision.`}
                </p>
              </div>

              <div className="grid xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="px-6 py-6">
                  <p className="whitespace-pre-wrap text-[15.5px] leading-[1.8] text-ink-900">{selected.current_version?.body}</p>
                </div>

                <div className="space-y-6 border-t border-line px-5 py-5 xl:border-l xl:border-t-0">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-ink-400">Automated findings</p>
                    {!reviewCurrent ? (
                      <p className="mt-2 text-[13px] text-amber-800">This version was submitted without a current review.</p>
                    ) : open.length === 0 ? (
                      <p className="mt-2 text-[13px] text-ink-600">No open findings on this version.</p>
                    ) : (
                      <>
                        <p className="mt-2 text-[13px] text-ink-600">
                          {open.length} open{serious > 0 && `, ${serious} critical or high`}.
                        </p>
                        <ul className="mt-2 space-y-2">
                          {open.map((f) => (
                            <li key={f.id} className="text-[13px]">
                              <div className="flex items-center gap-2">
                                <SeverityTag severity={f.severity} />
                                <span className="text-ink-700">{CATEGORY_LABEL[f.category] ?? f.category}</span>
                              </div>
                              {f.start_offset !== f.end_offset && <p className="mt-0.5 font-serif font-semibold text-ink-900">“{f.matched_text}”</p>}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>

                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-ink-400">Discussion</p>
                    {selected.comments.length === 0 ? (
                      <p className="mt-2 text-[13px] text-ink-500">No comments yet.</p>
                    ) : (
                      <ul className="mt-2 space-y-3">
                        {selected.comments.map((c) => (
                          <li key={c.id} className="text-[13px]">
                            <p>
                              <span className="font-medium text-ink-900">{c.author_name}</span>
                              <span className="text-ink-500"> · {timeAgo(c.created_at)}</span>
                            </p>
                            <p className="mt-0.5 leading-relaxed text-ink-700">{c.text}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                    <form onSubmit={postComment} className="mt-3 space-y-2">
                      <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} placeholder={`Comment as ${actor.name}…`} className={inputCls} />
                      <div className="flex justify-end">
                        <Button size="sm" type="submit" disabled={!comment.trim()}>
                          Comment
                        </Button>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <DecisionModal
        decision={decision}
        busy={busy}
        onClose={() => setDecision(null)}
        onSubmit={decide}
        warning={
          decision === 'approved' && !reviewCurrent
            ? 'This version has not been reviewed against the rulebook.'
            : decision === 'approved' && serious > 0
              ? `${serious} critical or high finding${serious === 1 ? ' is' : 's are'} still open. Approving records that you accepted ${serious === 1 ? 'it' : 'them'}.`
              : undefined
        }
      />
    </Page>
  );
}
