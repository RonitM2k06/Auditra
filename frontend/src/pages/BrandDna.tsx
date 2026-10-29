import { useEffect, useState } from 'react';
import { AlertTriangle, FlaskConical, GitCompareArrows, ShieldQuestion } from 'lucide-react';
import { Button, CATEGORY_LABEL, cx, Field, inputCls, Page, PageHeader, PageSkeleton, Section, SeverityTag, useToast } from '../components/ui';
import type { Brand, BrandDna as Dna, RuleChange, Simulation, WorkspaceRole } from '../types';
import { Outcome, Proposals } from '../components/Proposals';
import { api } from '../api';

const STATUS_STYLE: Record<string, string> = {
  configured: 'bg-pine-50 text-pine-700 border-pine-200',
  thin: 'bg-amber-50 text-amber-800 border-amber-200',
  missing: 'bg-red-50 text-red-700 border-red-200',
};

type ChangeKind = 'disable' | 'severity' | 'add_prohibited' | 'replacement';

export function BrandDna({ brand, role, userId, navigate }: { brand: Brand; role: WorkspaceRole; userId: string; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [dna, setDna] = useState<Dna | null>(null);
  const [kind, setKind] = useState<ChangeKind>('add_prohibited');
  const [ruleId, setRuleId] = useState('');
  const [value, setValue] = useState('free trial');
  const [severity, setSeverity] = useState('high');
  const [sim, setSim] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastChange, setLastChange] = useState<RuleChange | null>(null);
  const [propTitle, setPropTitle] = useState('');
  const [propRationale, setPropRationale] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const canSimulate = role !== 'creator';

  useEffect(() => {
    api.getDna(brand.id).then((d) => {
      setDna(d);
      setRuleId(Object.keys(d.rules)[0] ?? '');
    }).catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  const run = async () => {
    let change: RuleChange;
    if (kind === 'disable') change = { op: 'disable', rule_id: ruleId };
    else if (kind === 'severity') change = { op: 'update', rule_id: ruleId, rule: { severity } };
    else if (kind === 'replacement') change = { op: 'update', rule_id: ruleId, rule: { suggested_replacement: value } };
    else change = { op: 'add', rule: { name: `Proposed: avoid “${value}”`, category: 'prohibited_term', match_pattern: value, severity, description: 'Proposed in simulation' } };
    setBusy(true);
    try {
      setSim(await api.simulate(brand.id, [change]));
      setLastChange(change);
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  if (!dna) return <PageSkeleton />;
  const s = dna.summary;
  const ruleName = (id: string) => dna.rules[id]?.name ?? (id.startsWith('proposed') ? 'Proposed rule' : 'Rule');

  return (
    <Page>
      <PageHeader
        title="Brand DNA"
        description="A structured profile of how this brand is governed, derived only from the configured rules, approved claims, sources, palette and policies. Nothing here is generated or inferred by a model."
      />

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ['Dimensions configured', s.dimensions_configured, 'text-pine-700'],
          ['Thin (one record)', s.dimensions_thin, 'text-amber-700'],
          ['Missing', s.dimensions_missing, s.dimensions_missing ? 'text-red-700' : 'text-ink-400'],
          ['Rule conflicts', s.definite_conflicts + s.possible_conflicts, s.definite_conflicts ? 'text-red-700' : 'text-ink-400'],
        ].map(([label, n, cls]) => (
          <div key={label as string} className="rounded-xl border border-line bg-white px-4 py-3">
            <p className={cx('text-[26px] font-semibold tabular-nums', cls as string)}>{n as number}</p>
            <p className="text-[12.5px] text-ink-500">{label}</p>
          </div>
        ))}
      </div>
      <p className="-mt-5 mb-8 text-[12px] text-ink-500">{dna.scoring_note}</p>

      <div className="grid gap-4 md:grid-cols-2">
        {dna.dimensions.map((d) => (
          <section key={d.key} className="flex flex-col rounded-xl border border-line bg-white">
            <header className="flex items-start gap-3 border-b border-line px-4 py-3">
              <div className="min-w-0 flex-1">
                <h3 className="text-[14.5px] font-semibold text-ink-900">{d.label}</h3>
                <p className="mt-0.5 text-[12.5px] leading-snug text-ink-500">{d.explanation}</p>
              </div>
              <span className={cx('shrink-0 rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide', STATUS_STYLE[d.status])}>{d.status}</span>
            </header>
            {d.items.length === 0 ? (
              <p className="px-4 py-4 text-[13px] italic text-ink-500">Nothing configured. {d.key === 'evidence' ? 'Add sources in the Evidence library.' : d.key === 'governance' || d.key === 'visual' ? 'Configure it under Governance.' : 'Add rules in the Rulebook.'}</p>
            ) : (
              <ul className="max-h-56 divide-y divide-line overflow-y-auto">
                {d.items.map((it, i) => (
                  <li key={i} className="flex items-start gap-2 px-4 py-2 text-[13px]">
                    {it.color && <span className="mt-0.5 h-4 w-4 shrink-0 rounded-sm border border-line" style={{ background: it.color }} />}
                    <div className="min-w-0 flex-1">
                      <p className={cx('text-ink-800', it.expired && 'line-through decoration-amber-500')}>{it.label}</p>
                      {it.detail && <p className="truncate font-mono text-[11.5px] text-ink-500" title={it.detail}>{it.detail}</p>}
                      {it.source && <p className="text-[11.5px] text-ink-400">{it.source}</p>}
                    </div>
                    {it.severity && <SeverityTag severity={it.severity} />}
                    {it.source_id && <button onClick={() => navigate('sources', it.source_id)} className="text-[12px] text-pine-700 hover:underline">open</button>}
                  </li>
                ))}
              </ul>
            )}
            {d.observed_findings !== undefined && d.observed_findings > 0 && (
              <p className="mt-auto border-t border-line px-4 py-2 text-[12px] text-ink-500">{d.observed_findings} finding(s) recorded in this dimension across all reviews.</p>
            )}
          </section>
        ))}
      </div>

      <Section title="Rulebook contradictions" description="Definite conflicts are logical: compliant content is impossible or a fix creates a new violation. Possible conflicts need a person to judge intent.">
        {dna.contradictions.length === 0 ? (
          <p className="rounded-lg border border-line bg-white px-4 py-4 text-[13px] text-ink-600">No contradictions detected among the active rules.</p>
        ) : (
          <ul className="space-y-2">
            {dna.contradictions.map((c, i) => (
              <li key={i} className={cx('rounded-lg border bg-white px-4 py-3', c.certainty === 'definite' ? 'border-red-200' : 'border-amber-200')}>
                <p className="flex items-center gap-2 text-[14px] font-medium text-ink-900">
                  {c.certainty === 'definite' ? <AlertTriangle className="h-4 w-4 text-red-600" /> : <ShieldQuestion className="h-4 w-4 text-amber-600" />}
                  {c.title}
                  <span className={cx('ml-auto rounded px-1.5 text-[11px] font-semibold uppercase', c.certainty === 'definite' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-800')}>{c.certainty}</span>
                </p>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-700">{c.explanation}</p>
                <p className="mt-1.5 flex flex-wrap gap-1.5 text-[12px]">
                  {c.rule_ids.map((id) => <span key={id} className="rounded bg-ink-100 px-1.5 py-0.5 text-ink-600">{ruleName(id)}</span>)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Rule-change simulator" description="Preview what a proposed change would do to every item’s current version. Runs entirely in memory: the active rulebook, findings and approvals are not touched.">
        {!canSimulate ? (
          <p className="rounded-lg border border-line bg-white px-4 py-3 text-[13px] text-ink-600">Simulations are available to reviewers and admins.</p>
        ) : (
          <div className="rounded-xl border border-line bg-white p-4">
            <div className="grid gap-3 sm:grid-cols-[1.2fr_1fr_1fr_auto] sm:items-end">
              <Field label="Proposed change">
                <select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value as ChangeKind)}>
                  <option value="add_prohibited">Add a prohibited phrase</option>
                  <option value="disable">Disable an existing rule</option>
                  <option value="severity">Change a rule’s severity</option>
                  <option value="replacement">Change a suggested replacement</option>
                </select>
              </Field>
              {kind === 'add_prohibited' || kind === 'replacement' ? (
                <Field label={kind === 'add_prohibited' ? 'Phrase' : 'New replacement'}><input className={inputCls} value={value} onChange={(e) => setValue(e.target.value)} /></Field>
              ) : null}
              {kind !== 'add_prohibited' && (
                <Field label="Rule">
                  <select className={inputCls} value={ruleId} onChange={(e) => setRuleId(e.target.value)}>
                    {Object.entries(dna.rules).map(([id, r]) => <option key={id} value={id}>{r.name}</option>)}
                  </select>
                </Field>
              )}
              {(kind === 'severity' || kind === 'add_prohibited') && (
                <Field label="Severity">
                  <select className={inputCls} value={severity} onChange={(e) => setSeverity(e.target.value)}>
                    {['critical', 'high', 'medium', 'low'].map((x) => <option key={x}>{x}</option>)}
                  </select>
                </Field>
              )}
              <Button variant="primary" onClick={run} disabled={busy}><FlaskConical className="h-4 w-4" /> {busy ? 'Simulating…' : 'Simulate'}</Button>
            </div>

            {sim && (
              <div className="mt-5">
                <p className="flex items-center gap-2 text-[13px] text-ink-700">
                  <GitCompareArrows className="h-4 w-4 text-ink-400" />
                  <span><b>{sim.affected_items}</b> of {sim.items.length} items would change. {sim.note}</span>
                </p>
                {sim.new_contradictions.length > 0 && (
                  <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-800">
                    This change introduces {sim.new_contradictions.length} new rule conflict(s): {sim.new_contradictions.map((c) => c.title).join('; ')}.
                  </div>
                )}
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-[13px]">
                    <thead className="text-[11px] uppercase tracking-wider text-ink-400">
                      <tr><th className="py-2 font-medium">Content (current version)</th><th className="font-medium">Outcome</th><th className="font-medium">Findings</th><th className="font-medium">Gained</th><th className="font-medium">Lost</th><th className="font-medium">Policy impact</th></tr>
                    </thead>
                    <tbody>
                      {sim.items.filter((i) => i.gained.length || i.lost.length || i.severity_changed.length || i.policies_added.length || i.policies_removed.length).map((i) => (
                        <tr key={i.content_id} className="border-t border-line align-top">
                          <td className="py-2 pr-3">
                            <button onClick={() => navigate('studio', i.content_id)} className="font-medium text-ink-900 hover:underline">{i.title}</button>
                            <p className="text-[12px] text-ink-500">v{i.version_number} · {i.status.replace('_', ' ')}</p>
                          </td>
                          <td className="py-2 pr-2"><span className="flex items-center gap-1"><Outcome value={i.outcome_before} />→<Outcome value={i.outcome_after} /></span></td>
                          <td className="py-2 tabular-nums text-ink-700">{i.findings_before} → {i.findings_after}</td>
                          <td className="py-2 pr-3">{i.gained.map((f, k) => <p key={k} className="text-red-700">+ {CATEGORY_LABEL[f.category] ?? f.category}: “{f.matched_text}”</p>)}</td>
                          <td className="py-2 pr-3">{i.lost.map((f, k) => <p key={k} className="text-pine-700">− {CATEGORY_LABEL[f.category] ?? f.category}: “{f.matched_text}”</p>)}{i.severity_changed.map((c, k) => <p key={`s${k}`} className="text-ink-600">“{c.after.matched_text}” {c.before.severity} → {c.after.severity}</p>)}</td>
                          <td className="py-2 text-[12.5px]">
                            {i.policies_added.map((p) => <p key={p} className="text-amber-800">now triggers: {p}</p>)}
                            {i.policies_removed.map((p) => <p key={p} className="text-ink-500">no longer triggers: {p}</p>)}
                            {i.approval_at_risk && <p className="font-medium text-red-700">Approved item would need re-approval</p>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {sim.affected_items === 0 && <p className="py-3 text-[13px] italic text-ink-500">No current content would gain or lose findings.</p>}
                </div>
                {lastChange && (
                  <form className="mt-4 grid gap-2 rounded-lg border border-dashed border-ink-300 p-3 sm:grid-cols-[1fr_1.4fr_auto] sm:items-end"
                    onSubmit={async (e) => {
                      e.preventDefault();
                      try {
                        await api.createProposal(brand.id, propTitle, propRationale, [lastChange]);
                        toast('Saved as a proposal. A workspace admin (not you) can activate it.', 'success');
                        setPropTitle('');
                        setPropRationale('');
                        setRefreshKey((k) => k + 1);
                      } catch (err: any) {
                        toast(err.message, 'error');
                      }
                    }}>
                    <Field label="Proposal title" required><input className={inputCls} value={propTitle} onChange={(e) => setPropTitle(e.target.value)} minLength={3} required /></Field>
                    <Field label="Rationale"><input className={inputCls} value={propRationale} onChange={(e) => setPropRationale(e.target.value)} /></Field>
                    <Button type="submit" variant="primary">Save as proposal</Button>
                  </form>
                )}
              </div>
            )}
          </div>
        )}
      </Section>

      <Section title="Rule-change proposals" description="Saved simulations awaiting a decision. Activating changes the live rulebook; it needs a workspace admin who did not propose it, explicit confirmation, and a simulation run against the current rulebook.">
        <Proposals brandId={brand.id} role={role} userId={userId} refreshKey={refreshKey} />
      </Section>
    </Page>
  );
}
