import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Button, EmptyState, Page, PageHeader, PageSkeleton, Section, SEV_META, SEVERITIES, STATUS_META, cx, timeAgo, useToast } from '../components/ui';
import { ContentTable } from '../components/ContentTable';
import type { Brand, DashboardStats } from '../types';
import { api } from '../api';

const STATUS_ORDER = ['draft', 'in_review', 'changes_requested', 'approved', 'rejected'];

export function Overview({ brand, navigate }: { brand: Brand; navigate: (page: string, id?: string | null) => void }) {
  const toast = useToast();
  const [s, setS] = useState<DashboardStats | null>(null);

  useEffect(() => {
    setS(null);
    api.getDashboard(brand.id).then(setS).catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  if (!s) return <PageSkeleton />;

  const attention = s.recent_reviews.filter((r) => r.status === 'in_review' || r.status === 'changes_requested');
  const totalOpen = SEVERITIES.reduce((n, k) => n + (s.severity_distribution[k] || 0), 0);

  const stats = [
    { label: 'Pieces of content', value: s.total_reviews, go: 'reviews' },
    { label: 'Waiting for approval', value: s.awaiting_approval, go: 'approvals' },
    { label: 'With open critical or high findings', value: s.high_severity_issues, go: 'reviews' },
    { label: 'Approved', value: s.approved_reviews, go: 'reviews' },
  ];

  return (
    <Page>
      <PageHeader
        title="Overview"
        description={
          <>
            {brand.name}, all content, all time.{brand.is_sample && ' This workspace contains fictional demonstration data.'}
          </>
        }
        actions={
          <>
            <Button onClick={() => navigate('rulebook')}>Open rulebook</Button>
            <Button variant="primary" onClick={() => navigate('studio')}>
              <Plus className="h-3.5 w-3.5" /> New review
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-line bg-white lg:grid-cols-4">
        {stats.map((st, i) => (
          <button
            key={st.label}
            onClick={() => navigate(st.go)}
            className={cx('px-5 py-4 text-left transition-colors hover:bg-ink-50', i % 2 === 1 && 'border-l border-line', i >= 2 && 'border-t border-line lg:border-t-0', i === 2 && 'lg:border-l')}
          >
            <p className="text-[12.5px] text-ink-500">{st.label}</p>
            <p className="mt-1 font-serif text-[30px] leading-none tabular-nums text-ink-900">{st.value}</p>
          </button>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        <div className="space-y-8 lg:col-span-2">
          <Section title="Needs attention" description="Submitted pieces and pieces sent back to their authors.">
            <ContentTable
              items={attention}
              onOpen={(id) => navigate('studio', id)}
              empty={<EmptyState title="Nothing is waiting on anyone" body="Submitted content and requested changes will show up here." />}
            />
          </Section>
          <Section
            title="Recently updated"
            action={
              <button onClick={() => navigate('reviews')} className="text-[12.5px] text-ink-500 hover:text-ink-900">
                All content →
              </button>
            }
          >
            <ContentTable
              items={s.recent_reviews}
              onOpen={(id) => navigate('studio', id)}
              empty={<EmptyState title="No content yet" body="Start a review to check your first piece." action={<Button variant="primary" onClick={() => navigate('studio')}>New review</Button>} />}
            />
          </Section>
        </div>

        <div className="space-y-8">
          <Section title="Workflow status">
            <div className="rounded-lg border border-line bg-white p-4">
              <div className="flex h-2 overflow-hidden rounded-full bg-ink-100">
                {STATUS_ORDER.map((k) =>
                  s.status_counts[k] ? <div key={k} className={STATUS_META[k].dot} style={{ width: `${(s.status_counts[k] / Math.max(1, s.total_reviews)) * 100}%` }} /> : null,
                )}
              </div>
              <ul className="mt-3 space-y-1.5 text-[13px]">
                {STATUS_ORDER.map((k) => (
                  <li key={k} className="flex items-center gap-2">
                    <span className={cx('h-2 w-2 rounded-full', STATUS_META[k].dot)} />
                    <span className="flex-1 text-ink-700">{STATUS_META[k].label}</span>
                    <span className="tabular-nums text-ink-500">{s.status_counts[k] || 0}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Section>

          <Section title="Open findings" description="Unresolved findings on each piece's current version.">
            <div className="rounded-lg border border-line bg-white p-4">
              {totalOpen === 0 ? (
                <p className="text-[13px] text-ink-500">No open findings on current versions.</p>
              ) : (
                <ul className="space-y-2.5 text-[13px]">
                  {SEVERITIES.map((k) => {
                    const n = s.severity_distribution[k] || 0;
                    return (
                      <li key={k}>
                        <div className="flex justify-between">
                          <span className="text-ink-700">{SEV_META[k].label}</span>
                          <span className="tabular-nums text-ink-500">{n}</span>
                        </div>
                        <div className="mt-1 h-1 rounded-full bg-ink-100">
                          <div className={cx('h-1 rounded-full', SEV_META[k].bar)} style={{ width: `${(n / totalOpen) * 100}%` }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </Section>

          <Section
            title="Activity"
            action={
              <button onClick={() => navigate('audit')} className="text-[12.5px] text-ink-500 hover:text-ink-900">
                Audit trail →
              </button>
            }
          >
            {s.recent_activity.length === 0 ? (
              <p className="text-[13px] text-ink-500">No activity yet.</p>
            ) : (
              <ul className="space-y-3">
                {s.recent_activity.slice(0, 6).map((e) => (
                  <li key={e.id} className="text-[13px]">
                    <p className="leading-snug text-ink-800">{e.description}</p>
                    <p className="mt-0.5 text-[12px] text-ink-500">
                      {e.actor_name} · {timeAgo(e.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>
    </Page>
  );
}
