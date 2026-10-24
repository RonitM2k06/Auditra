import React, { useEffect, useState } from 'react';
import { CATEGORY_LABEL, EmptyState, Page, PageHeader, PageSkeleton, Section, SeverityTag, timeAgo, useToast } from '../components/ui';
import type { Brand, GovernanceInsights } from '../types';
import { api } from '../api';

function HowCalculated({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-[12px] leading-relaxed text-ink-400">{children}</p>;
}

export function Insights({ brand }: { brand: Brand }) {
  const toast = useToast();
  const [data, setData] = useState<GovernanceInsights | null>(null);

  useEffect(() => {
    setData(null);
    api.getInsights(brand.id).then(setData).catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  if (!data) return <PageSkeleton />;

  const t = data.approval_turnaround_summary as GovernanceInsights['approval_turnaround_summary'] & { average_turnaround_hours: number | null; turnaround_sample_size?: number };
  const maxCat = Math.max(1, ...data.most_frequent_categories.map((c) => c.count));
  const noData = data.most_frequent_categories.length === 0;

  return (
    <Page width="max-w-5xl">
      <PageHeader title="Governance insights" description={`Patterns across every review run in ${brand.name}. Small samples, so read these as prompts for a conversation rather than conclusions.`} />

      <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-line bg-white lg:grid-cols-4">
        {[
          { label: 'Decisions recorded', value: t.total_governance_decisions },
          { label: 'Share approved', value: t.total_governance_decisions ? t.first_pass_approval_rate : '—' },
          { label: 'Changes requested', value: t.changes_requested_count },
          { label: 'Avg. submit → decision', value: t.average_turnaround_hours == null ? '—' : `${t.average_turnaround_hours}h` },
        ].map((s, i) => (
          <div key={s.label} className={`px-5 py-4 ${i % 2 ? 'border-l border-line' : ''} ${i >= 2 ? 'border-t border-line lg:border-t-0' : ''} ${i === 2 ? 'lg:border-l' : ''}`}>
            <p className="text-[12.5px] text-ink-500">{s.label}</p>
            <p className="mt-1 font-serif font-semibold text-[28px] leading-none tabular-nums text-ink-900">{s.value}</p>
          </div>
        ))}
      </div>
      <HowCalculated>
        Share approved = approvals ÷ all reviewer decisions. Turnaround = time between the latest “submitted” event and each decision
        {t.turnaround_sample_size ? `, averaged over ${t.turnaround_sample_size} decision${t.turnaround_sample_size === 1 ? '' : 's'}` : '; no decision has a matching submission yet'}.
      </HowCalculated>

      {noData ? (
        <EmptyState title="Not enough data yet" body="Run a few reviews and these sections will fill in." />
      ) : (
        <div className="grid gap-8 lg:grid-cols-2">
          <Section title="Findings by category">
            <ul className="space-y-3 rounded-lg border border-line bg-white p-4">
              {data.most_frequent_categories.map((c) => (
                <li key={c.category} className="text-[13px]">
                  <div className="flex justify-between">
                    <span className="text-ink-800">{CATEGORY_LABEL[c.category] ?? c.category}</span>
                    <span className="tabular-nums text-ink-500">
                      {c.count} · {c.percentage}%
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-ink-100">
                    <div className="h-1.5 rounded-full bg-pine-600" style={{ width: `${(c.count / maxCat) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
            <HowCalculated>Every finding from every review run, including runs on earlier versions. Re-running a review counts its findings again.</HowCalculated>
          </Section>

          <Section title="Rules triggered most">
            {data.most_triggered_rules.length === 0 ? (
              <p className="text-[13px] text-ink-500">No rulebook rules have been triggered yet.</p>
            ) : (
              <ol className="divide-y divide-line rounded-lg border border-line bg-white">
                {data.most_triggered_rules.map((r, i) => (
                  <li key={r.rule_id} className="flex items-center gap-3 px-4 py-2.5 text-[13px]">
                    <span className="w-4 tabular-nums text-ink-400">{i + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-ink-800">{r.rule_name}</span>
                    <SeverityTag severity={r.severity} />
                    <span className="w-8 text-right tabular-nums text-ink-500">{r.trigger_count}×</span>
                  </li>
                ))}
              </ol>
            )}
            <HowCalculated>Counts findings linked to a rulebook rule. Built-in checks and AI suggestions without a rule are excluded.</HowCalculated>
          </Section>
        </div>
      )}

      {data.recurring_unresolved_issues.length > 0 && (
        <Section title="Unresolved critical and high findings" description="Not applied or dismissed, across all review runs (latest first).">
          <ul className="divide-y divide-line rounded-lg border border-line bg-white">
            {data.recurring_unresolved_issues.map((f) => (
              <li key={f.id} className="flex flex-col gap-1 px-4 py-3 text-[13px] sm:flex-row sm:items-center sm:gap-4">
                <SeverityTag severity={f.severity} />
                <span className="w-36 shrink-0 text-ink-500">{CATEGORY_LABEL[f.category] ?? f.category}</span>
                <span className="min-w-0 flex-1 truncate font-serif font-semibold text-[14px] text-ink-900">“{f.matched_text}”</span>
                <span className="shrink-0 text-[12px] text-ink-400">{timeAgo(f.created_at)}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {data.rule_clarity_insights.length > 0 && (
        <Section title="Things worth discussing" description="Generated from the counts above using simple rules. They are hypotheses, not findings.">
          <div className="grid gap-4 md:grid-cols-2">
            {data.rule_clarity_insights.map((h, i) => (
              <div key={i} className="rounded-lg border border-line bg-white p-4 text-[13px]">
                <p className="font-medium text-ink-900">{h.title}</p>
                <p className="mt-1.5 leading-relaxed text-ink-600">{h.hypothesis}</p>
                <p className="mt-2 leading-relaxed text-ink-800">
                  <span className="text-ink-500">Could try: </span>
                  {h.recommendation}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </Page>
  );
}
