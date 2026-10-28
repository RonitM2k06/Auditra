import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, RefreshCw, XCircle } from 'lucide-react';
import { Button, cx, Field, formatDateTime, inputCls, Modal, useToast } from './ui';
import type { RuleChange, Simulation } from '../types';
import { api } from '../api';

export interface Proposal {
  id: string;
  title: string;
  rationale: string | null;
  status: 'proposed' | 'activated' | 'rejected';
  changes: RuleChange[];
  simulation: Simulation;
  summary: { assets_evaluated: number; affected: number; new_failures: string[]; newly_passing: string[]; new_reviews: string[]; approvals_at_risk: string[]; new_contradictions: number };
  proposed_by: string;
  proposed_by_user_id: string;
  decided_by: string | null;
  decision_note: string | null;
  simulated_at: string;
  simulation_is_current: boolean;
  scope_note: string;
}

const OUTCOME: Record<string, string> = { pass: 'text-pine-700 bg-pine-50', review: 'text-amber-800 bg-amber-50', fail: 'text-red-700 bg-red-50' };

export function Outcome({ value }: { value: string }) {
  return <span className={cx('rounded px-1.5 py-px text-[11.5px] font-semibold uppercase', OUTCOME[value])}>{value}</span>;
}

export function Proposals({ brandId, role, userId, refreshKey }: { brandId: string; role: string; userId: string; refreshKey: number }) {
  const toast = useToast();
  const [list, setList] = useState<Proposal[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [deciding, setDeciding] = useState<{ p: Proposal; decision: 'activate' | 'reject' } | null>(null);
  const [note, setNote] = useState('');
  const [confirm, setConfirm] = useState(false);

  const load = useCallback(() => api.getProposals(brandId).then(setList).catch((e) => toast(e.message, 'error')), [brandId, toast]);
  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      toast(ok, 'success');
      setDeciding(null);
      load();
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (!list) return null;
  if (!list.length) return <p className="rounded-lg border border-line bg-white px-4 py-3 text-[13px] text-ink-600">No proposals yet. Run a simulation above and save it as a proposal.</p>;

  return (
    <>
      <ul className="space-y-2">
        {list.map((p) => {
          const isOpen = open === p.id;
          const s = p.summary;
          return (
            <li key={p.id} className="rounded-xl border border-line bg-white">
              <button onClick={() => setOpen(isOpen ? null : p.id)} className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left hover:bg-ink-50" aria-expanded={isOpen}>
                <span className={cx('rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase',
                  p.status === 'activated' ? 'bg-pine-50 text-pine-700' : p.status === 'rejected' ? 'bg-ink-100 text-ink-600' : 'bg-sky-50 text-sky-800')}>{p.status}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-medium text-ink-900">{p.title}</span>
                  <span className="block text-[12px] text-ink-500">by {p.proposed_by} · simulated {formatDateTime(p.simulated_at)} on {s.assets_evaluated} item(s)</span>
                </span>
                <span className="text-[12px] text-ink-600">
                  <b className="text-red-700">{s.new_failures.length}</b> new fail · <b className="text-pine-700">{s.newly_passing.length}</b> newly pass · <b className="text-amber-700">{s.new_reviews.length}</b> new review
                </span>
              </button>
              {isOpen && (
                <div className="space-y-3 border-t border-line px-4 py-3 text-[13px]">
                  {p.rationale && <p className="text-ink-700"><span className="font-medium">Rationale: </span>{p.rationale}</p>}
                  <p className="font-mono text-[12px] text-ink-600">{p.changes.map((c) => `${c.op}${c.rule?.match_pattern ? ` "${c.rule.match_pattern}"` : ''}${c.rule?.severity ? ` (${c.rule.severity})` : ''}`).join(' · ')}</p>
                  {!p.simulation_is_current && <p className="rounded-md bg-amber-50 px-3 py-2 text-amber-900">The rulebook changed after this simulation. Re-run it before deciding.</p>}
                  {s.approvals_at_risk.length > 0 && <p className="text-red-700">Approved items that would need re-approval: {s.approvals_at_risk.join(', ')}</p>}
                  {s.new_contradictions > 0 && <p className="text-red-700">Introduces {s.new_contradictions} new rule conflict(s).</p>}
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[520px] text-left text-[12.5px]">
                      <thead className="text-[11px] uppercase tracking-wider text-ink-400"><tr><th className="py-1.5 font-medium">Item (current version)</th><th className="font-medium">Before</th><th className="font-medium">After</th><th className="font-medium">Because of</th></tr></thead>
                      <tbody>
                        {p.simulation.items.filter((i) => i.outcome_before !== i.outcome_after || i.gained.length || i.lost.length).map((i) => (
                          <tr key={i.content_id} className="border-t border-line align-top">
                            <td className="py-1.5 pr-2 text-ink-800">{i.title} <span className="text-ink-400">v{i.version_number}</span></td>
                            <td className="py-1.5"><Outcome value={i.outcome_before} /></td>
                            <td className="py-1.5"><Outcome value={i.outcome_after} /></td>
                            <td className="py-1.5 text-ink-600">{i.responsible_rules.join(', ')}{i.gained[0] ? ` — “${i.gained[0].matched_text}”` : ''}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-[11.5px] text-ink-500">{p.scope_note}</p>
                  {p.status === 'proposed' ? (
                    <div className="flex flex-wrap gap-2">
                      {role !== 'creator' && <Button size="sm" onClick={() => act(() => api.rerunProposal(p.id), 'Simulation re-run.')}><RefreshCw className="h-3.5 w-3.5" /> Re-run simulation</Button>}
                      {role === 'admin' && (
                        <>
                          <Button size="sm" variant="primary" disabled={p.proposed_by_user_id === userId || !p.simulation_is_current}
                            title={p.proposed_by_user_id === userId ? 'Another admin must activate your proposal' : undefined}
                            onClick={() => { setDeciding({ p, decision: 'activate' }); setNote(''); setConfirm(false); }}>
                            <CheckCircle2 className="h-3.5 w-3.5" /> Activate…
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => { setDeciding({ p, decision: 'reject' }); setNote(''); }}><XCircle className="h-3.5 w-3.5" /> Reject…</Button>
                        </>
                      )}
                      {role !== 'admin' && <span className="self-center text-[12px] text-ink-500">Only a workspace admin (not the proposer) can activate or reject.</span>}
                    </div>
                  ) : (
                    <p className="text-ink-600">{p.status === 'activated' ? 'Activated' : 'Rejected'} by {p.decided_by}{p.decision_note ? `: ${p.decision_note}` : ''}</p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <Modal open={!!deciding} onClose={() => setDeciding(null)}
        title={deciding?.decision === 'activate' ? `Activate “${deciding?.p.title}”?` : `Reject “${deciding?.p.title}”?`}
        description={deciding?.decision === 'activate' ? 'This changes the live rulebook for everyone in the workspace. Existing analyses keep their recorded rulebook; re-run analyses to apply the new rules.' : 'The proposal is closed and the rulebook stays as it is.'}
        footer={<>
          <Button onClick={() => setDeciding(null)}>Cancel</Button>
          <Button variant={deciding?.decision === 'activate' ? 'primary' : 'dangerSolid'}
            disabled={deciding?.decision === 'activate' ? !confirm : !note.trim()}
            onClick={() => deciding && act(() => api.decideProposal(deciding.p.id, deciding.decision, confirm, note), deciding.decision === 'activate' ? 'Rule change activated.' : 'Proposal rejected.')}>
            {deciding?.decision === 'activate' ? 'Activate' : 'Reject'}
          </Button>
        </>}>
        {deciding?.decision === 'activate' && (
          <label className="mb-3 flex items-start gap-2 text-[13px] text-ink-800">
            <input type="checkbox" className="mt-0.5 accent-pine-600" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
            I reviewed the simulated impact: {deciding.p.summary.new_failures.length} new failure(s), {deciding.p.summary.newly_passing.length} newly passing.
          </label>
        )}
        <Field label={deciding?.decision === 'reject' ? 'Reason (required)' : 'Note (optional)'}>
          <textarea rows={3} className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </Modal>
    </>
  );
}
