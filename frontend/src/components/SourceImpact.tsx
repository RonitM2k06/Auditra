import { useCallback, useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { Button, ClaimBadge, cx, Section, useToast } from './ui';
import { api, type ImpactClaim, type ReverifyResult, type SourceImpactData } from '../api';

const FRESH: Record<string, { label: string; cls: string }> = {
  expired: { label: 'Expired', cls: 'border-red-200 bg-red-50 text-red-800' },
  retired: { label: 'Retired', cls: 'border-ink-200 bg-ink-50 text-ink-700' },
  review_overdue: { label: 'Review overdue', cls: 'border-amber-200 bg-amber-50 text-amber-900' },
  undated: { label: 'Undated', cls: 'border-ink-200 bg-white text-ink-600' },
  current: { label: 'Current', cls: 'border-pine-200 bg-pine-50 text-pine-800' },
};

const RELATION: Record<string, string> = {
  confirmed: 'Confirmed: cited by the current review',
  historical: 'Historical: earlier review or version',
  possible: 'Possible: named, not cited',
  missing_source: 'Source record deleted',
};

function ClaimRow({ c, navigate }: { c: ImpactClaim; navigate: (p: string, id?: string | null) => void }) {
  return (
    <li className="rounded-lg border border-line bg-white px-3 py-2 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <ClaimBadge status={c.status} />
        <span className={cx('rounded px-1.5 text-[11px] font-medium', c.relation === 'confirmed' ? 'bg-ink-900 text-white' : 'bg-ink-100 text-ink-600')}>{RELATION[c.relation]}</span>
        <button className="ml-auto text-pine-700 hover:underline" onClick={() => navigate('studio', `${c.content_id}?tab=claims`)}>{c.title} · v{c.version_number}</button>
      </div>
      <p className="mt-1 text-ink-800">“{c.claim_text}”</p>
      {c.passage_text && <p className="mt-1 border-l-2 border-line pl-2 text-ink-500">{c.passage_text}</p>}
      <p className="mt-1 text-[11.5px] text-ink-400">{c.basis} Check {c.claim_check_id.slice(0, 8)}{c.checked_at ? ` · ${c.checked_at.slice(0, 16).replace('T', ' ')}` : ''}</p>
    </li>
  );
}

export function SourceImpact({ brandId, canReverify, navigate }: { brandId: string; canReverify: boolean; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [data, setData] = useState<SourceImpactData | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ReverifyResult[]>>({});

  const load = useCallback(() => api.getSourceImpact(brandId).then(setData).catch((e) => toast(e.message, 'error')), [brandId, toast]);
  useEffect(() => {
    load();
  }, [load]);

  const reverify = async (sourceId: string, ids?: string[]) => {
    setRunning(sourceId);
    try {
      const r = await api.reverifySource(brandId, sourceId, ids);
      setResults((m) => {
        // A retry replaces only the retried rows.
        const prev = ids ? (m[sourceId] ?? []).filter((x) => !ids.includes(x.content_id)) : [];
        return { ...m, [sourceId]: [...prev, ...r.results] };
      });
      const failed = r.results.filter((x) => x.outcome === 'failed').length;
      toast(failed ? `${failed} of ${r.results.length} failed. Retry them below.` : `Re-verified ${r.results.length} asset(s).`, failed ? 'error' : 'success');
      load();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setRunning(null);
    }
  };

  if (!data) return null;
  const affected = data.sources.filter((s) => s.affects);

  return (
    <Section
      title="Freshness impact"
      description={<>{affected.length} of {data.sources.length} source(s) are expired, retired or overdue for review. {data.method}</>}
    >
      <ul className="space-y-2">
        {data.sources.map((s) => {
          const f = FRESH[s.freshness.status] ?? FRESH.undated;
          const isOpen = open === s.id;
          const res = results[s.id];
          const failed = res?.filter((r) => r.outcome === 'failed') ?? [];
          return (
            <li key={s.id} className="rounded-xl border border-line bg-white">
              <button className="flex w-full items-center gap-3 px-4 py-3 text-left" onClick={() => setOpen(isOpen ? null : s.id)} aria-expanded={isOpen}>
                {isOpen ? <ChevronDown className="h-4 w-4 text-ink-400" /> : <ChevronRight className="h-4 w-4 text-ink-400" />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13.5px] font-medium text-ink-900">{s.name}</span>
                  <span className="block text-[12px] text-ink-500">{s.freshness.reason}</span>
                </span>
                <span className="hidden text-right text-[12px] text-ink-500 sm:block">
                  {s.claims.filter((c) => c.relation === 'confirmed').length} confirmed claim(s) · {s.assets.length} asset(s) · {s.campaigns.length} campaign(s)
                  {s.possible.length > 0 && <> · {s.possible.length} possible</>}
                </span>
                <span className={cx('rounded border px-1.5 py-px text-[11px] font-semibold', f.cls)}>{f.label}</span>
              </button>
              {isOpen && (
                <div className="space-y-3 border-t border-line px-4 py-3 text-[13px]">
                  <dl className="grid grid-cols-2 gap-2 text-[12px] sm:grid-cols-4">
                    {[['Effective', s.effective_date], ['Expiry', s.expiry_date], ['Review by', s.review_date], ['Status', s.approval_status]].map(([k, v]) => (
                      <div key={k as string}><dt className="text-ink-400">{k}</dt><dd className={v ? 'text-ink-800' : 'italic text-ink-400'}>{v || 'not supplied'}</dd></div>
                    ))}
                  </dl>
                  {s.notes.map((n) => <p key={n} className="rounded-lg bg-ink-50 px-3 py-2 text-[12.5px] text-ink-600">{n}</p>)}

                  {s.assets.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-ink-500">Affected assets and campaigns</h4>
                      <ul className="space-y-1 text-[12.5px]">
                        {s.assets.map((a) => (
                          <li key={a.content_id} className="flex flex-wrap gap-2">
                            <button className="text-pine-700 hover:underline" onClick={() => navigate('studio', a.content_id)}>{a.title}</button>
                            <span className="text-ink-500">v{a.version_number} · {a.status.replace('_', ' ')} · {a.claims} claim(s){a.approved ? ' · approved' : ''}</span>
                          </li>
                        ))}
                        {s.campaigns.map((c) => (
                          <li key={c.id} className="text-ink-600">
                            Campaign <button className="text-pine-700 hover:underline" onClick={() => navigate('campaigns', c.id)}>{c.name}</button> — {c.basis}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {s.claims.length > 0 && <ul className="space-y-1.5">{s.claims.map((c) => <ClaimRow key={c.claim_check_id} c={c} navigate={navigate} />)}</ul>}
                  {s.possible.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-ink-500">Possible associations (not re-verified automatically)</h4>
                      <ul className="space-y-1.5">{s.possible.map((c) => <ClaimRow key={c.claim_check_id} c={c} navigate={navigate} />)}</ul>
                    </div>
                  )}

                  {s.assets.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2">
                      {canReverify ? (
                        <Button size="sm" variant="primary" disabled={running === s.id} onClick={() => reverify(s.id)}>
                          <RefreshCw className={cx('h-3.5 w-3.5', running === s.id && 'animate-spin')} /> Re-verify affected ({s.assets.length})
                        </Button>
                      ) : (
                        <span className="text-[12px] text-ink-500">Only reviewers and admins can re-verify.</span>
                      )}
                      <span className="text-[12px] text-ink-500">Re-runs the normal analysis. It never approves, publishes or marks a claim supported.</span>
                    </div>
                  )}

                  {res && (
                    <ul className="space-y-1 text-[12.5px]">
                      {res.map((r) => (
                        <li key={r.content_id} className={cx('rounded-lg px-3 py-1.5', r.outcome === 'ok' ? 'bg-pine-50 text-pine-900' : 'bg-red-50 text-red-800')}>
                          <span className="font-medium">{r.title}</span>:{' '}
                          {r.outcome === 'ok'
                            ? <>re-checked v{r.version_number}. Before: {r.before.join(', ') || 'none'} → after: {r.after?.join(', ') || 'no longer cites this source'}. {r.approval_satisfied ? 'Approval requirements still met.' : 'Not approvable as is.'}</>
                            : <>failed — {r.error}</>}
                        </li>
                      ))}
                      {failed.length > 0 && canReverify && (
                        <li><Button size="sm" disabled={running === s.id} onClick={() => reverify(s.id, failed.map((x) => x.content_id))}>Retry {failed.length} failed</Button></li>
                      )}
                    </ul>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {data.missing_sources.length > 0 && (
        <div className="mt-4">
          <h4 className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-ink-500">Citations to deleted sources</h4>
          <ul className="space-y-1.5">{data.missing_sources.map((c) => <ClaimRow key={c.claim_check_id} c={c} navigate={navigate} />)}</ul>
        </div>
      )}
    </Section>
  );
}
