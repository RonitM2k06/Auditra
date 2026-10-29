import { useEffect, useState } from 'react';
import { AlertOctagon, ArrowRight, CircleHelp, FileText, ShieldAlert } from 'lucide-react';
import { CATEGORY_LABEL, cx, EmptyState, PageSkeleton, SeverityTag, SEV_META, useToast } from './ui';
import { api } from '../api';

export interface RiskItem {
  id: string;
  severity: string;
  kind: 'finding' | 'claim' | 'conflict' | 'approval';
  category: string;
  source: string;
  basis: 'detected' | 'heuristic';
  title: string;
  evidence: {
    text?: string | null;
    explanation?: string;
    passage?: string | null;
    source_name?: string | null;
    source_section?: string | null;
    source_expiry?: string | null;
    source_document_id?: string | null;
    source_reference?: string | null;
    passages?: Array<{ asset: string; asset_id: string; value: string; passage: string }>;
  };
  asset_ids: string[];
  action: string;
  link: { page: string; id: string; tab?: string };
  corroborated_by?: string[];
}

export interface RiskReport {
  level: string;
  complete: boolean;
  explanation: string;
  method: string;
  counts: Record<string, number>;
  risks: RiskItem[];
  assets: Array<{ content_id: string; title: string; status: string; analysed: boolean; version_number: number; approval_satisfied: boolean }>;
  unverified: Array<{ content_id: string; title: string; reason: string }>;
  basis_counts: { detected: number; heuristic: number };
}

const LEVEL_STYLE: Record<string, { label: string; cls: string }> = {
  critical: { label: 'Critical', cls: 'bg-red-600 text-white' },
  high: { label: 'High', cls: 'bg-amber-500 text-white' },
  medium: { label: 'Medium', cls: 'bg-orange-400 text-white' },
  low: { label: 'Low', cls: 'bg-sky-500 text-white' },
  none_detected: { label: 'No risks detected', cls: 'bg-pine-600 text-white' },
  unknown: { label: 'Unknown', cls: 'bg-ink-400 text-white' },
};
const KIND_LABEL: Record<string, string> = { finding: 'Rule / visual finding', claim: 'Claim evidence', conflict: 'Cross-asset conflict', approval: 'Approval' };

export function RiskRadar({ campaignId, navigate }: { campaignId: string; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [data, setData] = useState<RiskReport | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    api.getCampaignRisk(campaignId).then(setData).catch((e) => toast(e.message, 'error'));
  }, [campaignId, toast]);

  if (!data) return <PageSkeleton />;
  if (!data.assets.length) return <EmptyState title="No assets in this campaign" body="Add content to the campaign to assess its risk." />;

  const lvl = LEVEL_STYLE[data.level] ?? LEVEL_STYLE.unknown;
  const shown = data.risks.filter((r) => filter === 'all' || r.severity === filter);
  const go = (r: RiskItem) => navigate(r.link.page, r.link.tab ? `${r.link.id}?tab=${r.link.tab}` : r.link.id);

  return (
    <div className="space-y-5">
      <section className="grid gap-4 rounded-xl border border-line bg-white p-5 md:grid-cols-[auto_1fr]">
        <div className="flex flex-col items-start gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-400">Campaign risk level</p>
          <span className={cx('rounded-lg px-3 py-1.5 text-[18px] font-semibold', lvl.cls)}>{lvl.label}</span>
          {!data.complete && <span className="flex items-center gap-1 text-[12px] font-medium text-amber-800"><CircleHelp className="h-3.5 w-3.5" /> Incomplete assessment</span>}
        </div>
        <div className="min-w-0">
          <p className="text-[14px] text-ink-800">{data.explanation}</p>
          <div className="mt-3 grid grid-cols-4 gap-px overflow-hidden rounded-md border border-line bg-line text-center">
            {(['critical', 'high', 'medium', 'low'] as const).map((s) => (
              <button key={s} onClick={() => setFilter(filter === s ? 'all' : s)} aria-pressed={filter === s}
                className={cx('bg-white px-2 py-2 hover:bg-ink-50', filter === s && 'ring-1 ring-inset ring-pine-600')}>
                <span className={cx('block text-[20px] font-semibold tabular-nums', data.counts[s] ? SEV_META[s].text : 'text-ink-300')}>{data.counts[s]}</span>
                <span className="block text-[11.5px] text-ink-500">{SEV_META[s].label}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-ink-500">
            {data.basis_counts.detected} detected · {data.basis_counts.heuristic} heuristic estimate{data.basis_counts.heuristic === 1 ? '' : 's'} ·
            recomputed from current versions, rules and approvals each time this page loads.
          </p>
          <details className="mt-2 text-[12px] text-ink-500">
            <summary className="cursor-pointer font-medium text-ink-600">How is this calculated?</summary>
            <p className="mt-1 leading-relaxed">{data.method}</p>
          </details>
        </div>
      </section>

      {data.unverified.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="flex items-center gap-2 text-[13.5px] font-semibold text-amber-900"><ShieldAlert className="h-4 w-4" /> Not yet verified</p>
          <ul className="mt-2 space-y-1">
            {data.unverified.map((u) => (
              <li key={u.content_id} className="flex flex-wrap items-center gap-2 text-[13px] text-amber-900">
                <span className="font-medium">{u.title}</span><span className="text-amber-800">— {u.reason}</span>
                <button onClick={() => navigate('studio', u.content_id)} className="font-medium underline underline-offset-2">Analyse</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {shown.length === 0 ? (
        <p className="rounded-lg border border-line bg-white px-4 py-6 text-center text-[13px] text-ink-600">
          {data.risks.length ? 'No risks at this severity.' : data.complete ? 'No risks detected in the analysed versions.' : 'No risks detected yet in the analysed assets.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {shown.map((r) => {
            const isOpen = open === r.id;
            return (
              <li key={r.id} className={cx('rounded-xl border border-l-[3px] bg-white', SEV_META[r.severity]?.edge, 'border-line')}>
                <button onClick={() => setOpen(isOpen ? null : r.id)} aria-expanded={isOpen} className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-ink-50">
                  <SeverityTag severity={r.severity} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13.5px] font-medium text-ink-900">{r.title}</span>
                    {r.evidence.text && <span className="mt-0.5 block truncate text-[12.5px] text-ink-600">“{r.evidence.text}”</span>}
                  </span>
                  <span className="hidden shrink-0 text-right text-[11.5px] text-ink-500 sm:block">
                    {KIND_LABEL[r.kind]}<br />
                    <span className={r.basis === 'heuristic' ? 'text-amber-700' : 'text-ink-500'}>{r.basis}</span>
                  </span>
                </button>
                {isOpen && (
                  <div className="space-y-3 border-t border-line px-4 py-3 text-[13px]">
                    <p className="leading-relaxed text-ink-700">{r.evidence.explanation}</p>
                    {r.evidence.passage && (
                      <blockquote className="rounded-md border-l-[3px] border-pine-500 bg-paper px-3 py-2 text-ink-800">
                        “{r.evidence.passage}”
                        <span className="mt-1 flex items-center gap-1 text-[12px] text-ink-500"><FileText className="h-3 w-3" />{r.evidence.source_name}{r.evidence.source_section ? ` § ${r.evidence.source_section}` : ''}{r.evidence.source_expiry ? ` · expires ${r.evidence.source_expiry}` : ''}</span>
                      </blockquote>
                    )}
                    {r.evidence.passages && (
                      <div className="grid gap-2 md:grid-cols-2">
                        {r.evidence.passages.map((p, i) => (
                          <div key={i} className="rounded-md border border-line bg-paper px-3 py-2">
                            <p className="text-[11.5px] font-medium text-ink-600">{p.asset} · <span className="text-ink-900">{p.value}</span></p>
                            <p className="mt-0.5 text-ink-800">{p.passage}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {r.evidence.source_reference && <p className="text-[12px] text-ink-500">Rule source: {r.evidence.source_reference}</p>}
                    <div className="flex flex-wrap items-center gap-3 rounded-md bg-pine-50 px-3 py-2">
                      <AlertOctagon className="h-4 w-4 shrink-0 text-pine-700" />
                      <p className="flex-1 text-ink-800"><span className="font-medium">Recommended action: </span>{r.action}</p>
                      <button onClick={() => go(r)} className="flex items-center gap-1 font-medium text-pine-700 hover:underline">Open evidence <ArrowRight className="h-3.5 w-3.5" /></button>
                    </div>
                    <p className="text-[11.5px] text-ink-400">
                      Source: {r.source}{r.corroborated_by?.length ? ` · also found by ${r.corroborated_by.join(', ')} (counted once)` : ''} · {CATEGORY_LABEL[r.category] ?? r.category.replace(/_/g, ' ')}
                    </p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
