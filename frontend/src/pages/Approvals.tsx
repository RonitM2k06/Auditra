import React, { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import {
  ACTORS,
  Button,
  CATEGORY_LABEL,
  CONTENT_TYPES,
  EmptyState,
  Page,
  PageHeader,
  SeverityTag,
  Skeleton,
  cx,
  inputCls,
  timeAgo,
  useToast,
  type Role,
} from '../components/ui';
import { DecisionModal, type Decision } from '../components/DecisionModal';
import type { Brand, ContentItemDetail } from '../types';
import { api } from '../api';

interface ApprovalsProps {
  brand: Brand;
  role: Role;
  navigate: (page: string, id?: string | null) => void;
  onChanged: () => void;
}

export function Approvals({ brand, role, navigate, onChanged }: ApprovalsProps) {
  const toast = useToast();
  const actor = ACTORS[role];
  const canDecide = role !== 'creator';
  const [items, setItems] = useState<ContentItemDetail[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState('');

  const load = useCallback(async () => {
    try {
      const list = await api.getContentItems(brand.id, 'in_review');
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
        description="Content submitted for a human decision. Automated findings inform the decision; they never make it."
      />

      {!canDecide && (
        <div className="rounded-md border border-line bg-white px-4 py-3 text-[13px] text-ink-600">
          You're acting as {actor.name}, a creator. Switch to Sarah Chen in the sidebar to record decisions.
        </div>
      )}

      {items === null ? (
        <Skeleton className="h-96 w-full" />
      ) : items.length === 0 ? (
        <EmptyState title="The queue is empty" body="When someone submits a piece for approval, it shows up here." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <ul className="space-y-1.5">
            {items.map((i) => (
              <li key={i.id}>
                <button
                  onClick={() => setSelectedId(i.id)}
                  className={cx(
                    'w-full rounded-md border px-3 py-2.5 text-left transition-colors',
                    i.id === selectedId ? 'border-ink-900 bg-white' : 'border-line bg-white hover:border-ink-300',
                  )}
                >
                  <p className="truncate text-[13.5px] font-medium text-ink-900">{i.title}</p>
                  <p className="mt-0.5 text-[12px] text-ink-500">
                    {i.created_by} · v{i.current_version_number} · {timeAgo(i.updated_at)}
                  </p>
                </button>
              </li>
            ))}
          </ul>

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

              <div className="grid xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="px-6 py-6">
                  <p className="whitespace-pre-wrap font-serif text-[16.5px] leading-[1.75] text-ink-900">{selected.current_version?.body}</p>
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
                              {f.start_offset !== f.end_offset && <p className="mt-0.5 font-serif text-ink-900">“{f.matched_text}”</p>}
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
