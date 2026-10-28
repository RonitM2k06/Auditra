import React, { useEffect, useState } from 'react';
import { AlertTriangle, Check, Minus, ShieldAlert, X } from 'lucide-react';
import { cx, Page, PageHeader, PageSkeleton, SeverityTag, useToast } from '../components/ui';
import type { Brand } from '../types';
import { api } from '../api';

interface Cell { state: 'violated' | 'passed' | 'not_checked' | 'review' | 'n/a'; reason: string; finding_id?: string }
interface PolicyRow {
  id: string;
  kind: 'rule' | 'control';
  name: string;
  category: string;
  severity: string;
  active: boolean;
  check: string | null;
  source: { cited?: string | null; document_id?: string | null; document?: string | null; expiry_date?: string | null;
            documents?: Array<{ id: string; name: string; expiry_date: string | null; review_date: string | null; updated: string | null }> };
  conflicts: string[];
  flags: string[];
  cells: Record<string, Cell>;
}
export interface CoverageData {
  policies: PolicyRow[];
  assets: Array<{ content_id: string; title: string; media_kind: string; version_number: number; analysed: boolean }>;
  counts: Record<string, number>;
  unanalysed_assets: string[];
  flagged_policies: string[];
  complete: boolean;
  statement: string;
}

const CELL: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
  violated: { cls: 'bg-red-100 text-red-700', icon: <X className="h-3.5 w-3.5" />, label: 'Violated' },
  passed: { cls: 'bg-pine-100 text-pine-700', icon: <Check className="h-3.5 w-3.5" />, label: 'Passed' },
  review: { cls: 'bg-amber-100 text-amber-800', icon: <AlertTriangle className="h-3.5 w-3.5" />, label: 'Needs review' },
  not_checked: { cls: 'bg-white text-ink-400 ring-1 ring-inset ring-dashed ring-ink-300', icon: <span className="text-[11px] font-semibold">?</span>, label: 'Not checked' },
  'n/a': { cls: 'bg-ink-50 text-ink-300', icon: <Minus className="h-3.5 w-3.5" />, label: 'Not applicable' },
};

export function Coverage({ brand, navigate }: { brand: Brand; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [data, setData] = useState<CoverageData | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  useEffect(() => {
    api.getCoverage(brand.id).then(setData).catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  if (!data) return <PageSkeleton />;
  const rows = data.policies.filter((p) => !onlyFlagged || p.flags.length || Object.values(p.cells).some((c) => c.state === 'violated' || c.state === 'not_checked'));

  return (
    <Page width="max-w-[1400px]">
      <PageHeader
        title="Governance coverage map"
        description="Every policy, the check that enforces it, the source behind it, and its result on each asset's current version. 'Not checked' is shown separately from 'passed'."
      />

      <section className={cx('mb-5 flex items-start gap-3 rounded-xl border p-4', data.complete ? 'border-pine-200 bg-pine-50' : 'border-amber-200 bg-amber-50')}>
        <ShieldAlert className={cx('mt-0.5 h-5 w-5 shrink-0', data.complete ? 'text-pine-600' : 'text-amber-700')} />
        <div className="min-w-0 text-[13.5px]">
          <p className={cx('font-medium', data.complete ? 'text-pine-800' : 'text-amber-900')}>{data.statement}</p>
          <p className="mt-1 text-[12.5px] text-ink-600">
            {data.counts.violated} violated · {data.counts.review} need review · {data.counts.passed} passed · {data.counts.not_checked} not checked · {data.counts['n/a']} not applicable
            {data.flagged_policies.length > 0 && ` · ${data.flagged_policies.length} policies flagged`}
          </p>
          {data.unanalysed_assets.length > 0 && <p className="mt-1 text-[12.5px] text-amber-900">Never analysed: {data.unanalysed_assets.join(', ')}</p>}
        </div>
        <label className="ml-auto flex shrink-0 items-center gap-1.5 text-[12.5px] text-ink-700">
          <input type="checkbox" className="accent-pine-600" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} /> Gaps only
        </label>
      </section>

      <div className="mb-3 flex flex-wrap gap-3 text-[12px] text-ink-600">
        {Object.entries(CELL).map(([k, v]) => <span key={k} className="flex items-center gap-1.5"><span className={cx('grid h-5 w-5 place-items-center rounded', v.cls)}>{v.icon}</span>{v.label}</span>)}
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-white">
        <table className="w-full border-collapse text-left text-[12.5px]">
          <thead>
            <tr className="border-b border-line align-bottom">
              <th className="sticky left-0 z-10 min-w-[300px] bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Policy · check · source</th>
              {data.assets.map((a) => (
                <th key={a.content_id} className="h-36 w-10 px-1 align-bottom">
                  <button onClick={() => navigate('studio', a.content_id)} title={`${a.title} (v${a.version_number})`}
                    className={cx('mx-auto block max-h-32 truncate text-[11.5px] font-medium [writing-mode:vertical-rl] rotate-180 hover:text-pine-700', a.analysed ? 'text-ink-700' : 'text-amber-700')}>
                    {a.title}{a.media_kind === 'image' ? ' 🖼' : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id} className={cx('border-b border-line align-top', !p.active && 'opacity-50')}>
                <td className="sticky left-0 z-10 bg-white px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    {p.kind === 'control' ? <span className="rounded bg-navy-900 px-1.5 text-[10.5px] font-semibold uppercase text-white">control</span> : <SeverityTag severity={p.severity} />}
                    <button onClick={() => navigate(p.kind === 'rule' ? 'rulebook' : p.category === 'claim_verification' ? 'sources' : 'governance')} className="truncate text-left font-medium text-ink-900 hover:underline">{p.name}</button>
                  </div>
                  <p className="mt-0.5 text-[11.5px] text-ink-500">{p.check ?? <span className="text-red-700">No implemented check</span>}</p>
                  <p className="text-[11.5px] text-ink-500">
                    {p.source.document_id ? (
                      <button onClick={() => navigate('sources', p.source.document_id)} className="text-pine-700 hover:underline">{p.source.document}{p.source.expiry_date ? ` · expires ${p.source.expiry_date}` : ''}</button>
                    ) : p.source.documents ? (
                      p.source.documents.map((d, i) => (
                        <span key={d.id}>{i > 0 && ', '}<button onClick={() => navigate('sources', d.id)} className="text-pine-700 hover:underline">{d.name}</button>{d.expiry_date ? ` (expires ${d.expiry_date})` : d.review_date ? ` (review by ${d.review_date})` : ''}</span>
                      ))
                    ) : (p.source.cited ?? 'No source cited')}
                  </p>
                  {p.flags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {p.flags.map((f) => <span key={f} className="rounded bg-amber-50 px-1.5 text-[11px] text-amber-900">{f}</span>)}
                    </div>
                  )}
                </td>
                {data.assets.map((a) => {
                  const c = p.cells[a.content_id];
                  const meta = CELL[c.state];
                  return (
                    <td key={a.content_id} className="px-1 py-2 text-center">
                      <button
                        onClick={() => navigate('studio', c.state === 'violated' ? `${a.content_id}?tab=${p.category === 'claim_verification' ? 'claims' : 'findings'}` : a.content_id)}
                        title={`${meta.label}: ${c.reason}`} aria-label={`${p.name} on ${a.title}: ${meta.label}`}
                        className={cx('mx-auto grid h-6 w-6 place-items-center rounded', meta.cls)}>
                        {meta.icon}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[12px] text-ink-500">
        A rule counts as checked only if the analysis of the asset's current version ran with that rule active (from the stored rulebook snapshot). Hover a cell for the reason; click to open the evidence.
      </p>
    </Page>
  );
}
