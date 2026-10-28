import { useEffect, useState } from 'react';
import { ArrowLeft, FlaskConical } from 'lucide-react';
import { Button, CATEGORY_LABEL, cx, Field, formatDateTime, inputCls, Page, PageHeader, PageSkeleton, SeverityTag, useToast } from '../components/ui';
import type { Replay as ReplayData, ReplayFinding, SimulationItem, WorkspaceRole } from '../types';
import { api } from '../api';

function FindingList({ title, items, tone }: { title: string; items: ReplayFinding[]; tone: string }) {
  return (
    <div className="rounded-lg border border-line bg-white">
      <p className={cx('border-b border-line px-3 py-2 text-[12px] font-semibold uppercase tracking-wider', tone)}>{title} · {items.length}</p>
      {items.length === 0 ? (
        <p className="px-3 py-3 text-[12.5px] italic text-ink-400">None</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((f, i) => (
            <li key={i} className="px-3 py-2 text-[12.5px]">
              <span className="flex items-center gap-2"><SeverityTag severity={f.severity} /><span className="text-ink-700">{CATEGORY_LABEL[f.category] ?? f.category}</span></span>
              <span className="mt-1 block truncate font-medium text-ink-900">“{f.matched_text}”</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Replay({ contentId, role, navigate }: { contentId: string | null; role: WorkspaceRole; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const [data, setData] = useState<ReplayData | null>(null);
  const [range, setRange] = useState<{ from?: number; to?: number }>({});
  const [ruleId, setRuleId] = useState('');
  const [cf, setCf] = useState<SimulationItem | null>(null);

  useEffect(() => {
    if (!contentId) return;
    api.getReplay(contentId, range.from, range.to).then(setData).catch((e) => toast(e.message, 'error'));
  }, [contentId, range, toast]);

  if (!contentId) return <Page><PageHeader title="Decision replay" description="Open a content item and choose Replay to compare its versions." /></Page>;
  if (!data) return <PageSkeleton />;

  const versionsNums = data.versions.map((v) => v.version_number);
  const reviewed = data.versions.find((v) => v.version_number === data.to_version)?.reviewed;
  const ruleOptions = Array.from(new Map([...data.findings.persisted, ...data.findings.new, ...data.findings.changed.map((c) => c.after)].filter((f) => f.rule_id).map((f) => [f.rule_id!, `${CATEGORY_LABEL[f.category] ?? f.category}: “${f.matched_text}”`])).entries());

  const runCf = async () => {
    if (!ruleId) return;
    try {
      setCf(await api.counterfactual(data.content_id, data.to_version, [{ op: 'disable', rule_id: ruleId }]));
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  return (
    <Page width="max-w-6xl">
      <button onClick={() => navigate('studio', data.content_id)} className="mb-3 flex items-center gap-1 text-[13px] text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to the studio</button>
      <PageHeader title={`Decision replay · ${data.title}`} description="Reconstructs what changed between two versions using stored versions, review runs, rule snapshots and audit events. Nothing is inferred where no record exists." />

      <div className="mb-6 flex flex-wrap items-end gap-3">
        {(['from', 'to'] as const).map((k) => (
          <Field key={k} label={k === 'from' ? 'Compare version' : 'with version'}>
            <select className={inputCls} value={k === 'from' ? data.from_version : data.to_version}
              onChange={(e) => { setCf(null); setRange({ from: k === 'from' ? Number(e.target.value) : data.from_version, to: k === 'to' ? Number(e.target.value) : data.to_version }); }}>
              {versionsNums.map((n) => <option key={n} value={n}>v{n}</option>)}
            </select>
          </Field>
        ))}
        <p className="pb-2 text-[12.5px] text-ink-500">{data.versions.length} version(s) · {data.decisions.length} decision(s) · {data.publications.length} publication(s)</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <section className="rounded-xl border border-line bg-white">
            <h3 className="border-b border-line px-4 py-2.5 text-[13.5px] font-semibold text-ink-900">Text changes v{data.from_version} → v{data.to_version}</h3>
            <p className="whitespace-pre-wrap px-4 py-4 text-[14.5px] leading-[1.8] text-ink-900">
              {data.diff.map((d, i) => d.op === 'equal' ? <span key={i}>{d.text}</span>
                : d.op === 'insert' ? <ins key={i} className="rounded-sm bg-pine-100 px-0.5 text-pine-700 no-underline">{d.text}</ins>
                : <del key={i} className="rounded-sm bg-red-50 px-0.5 text-red-700">{d.text}</del>)}
            </p>
            {data.from_version === data.to_version && <p className="px-4 pb-3 text-[12.5px] italic text-ink-500">Same version selected on both sides.</p>}
          </section>

          <section>
            <h3 className="mb-2 text-[13.5px] font-semibold text-ink-900">Findings between the latest reviews of each version</h3>
            {!data.review_runs.from || !data.review_runs.to ? (
              <p className="rounded-lg border border-line bg-white px-4 py-3 text-[13px] text-ink-600">One of these versions was never analysed, so its findings can’t be compared.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <FindingList title="Resolved" items={data.findings.resolved} tone="text-pine-700" />
                <FindingList title="Newly introduced" items={data.findings.new} tone="text-red-700" />
                <FindingList title="Persisted" items={data.findings.persisted} tone="text-ink-600" />
                <FindingList title="Changed severity / evidence" items={data.findings.changed.map((c) => c.after)} tone="text-amber-800" />
              </div>
            )}
          </section>

          <section className="rounded-xl border border-line bg-white p-4">
            <h3 className="text-[13.5px] font-semibold text-ink-900">Rulebook at the time</h3>
            {data.rulebook.note ? (
              <p className="mt-1 text-[13px] text-ink-600">{data.rulebook.note}</p>
            ) : data.rulebook.diff && (
              <div className="mt-1 text-[13px] text-ink-700">
                {data.rulebook.diff.added.length + data.rulebook.diff.removed.length + data.rulebook.diff.changed.length === 0 ? (
                  <p>The same active rules applied to both reviews.</p>
                ) : (
                  <ul className="space-y-1">
                    {data.rulebook.diff.added.map((r) => <li key={r.id} className="text-pine-700">+ {r.name} was active for v{data.to_version} only</li>)}
                    {data.rulebook.diff.removed.map((r) => <li key={r.id} className="text-red-700">− {r.name} was active for v{data.from_version} only</li>)}
                    {data.rulebook.diff.changed.map((c) => <li key={c.after.id}>~ {c.after.name}: {c.fields.join(', ')} changed</li>)}
                  </ul>
                )}
              </div>
            )}
          </section>

          {role !== 'creator' && reviewed && (
            <section className="rounded-xl border border-line bg-white p-4">
              <h3 className="flex items-center gap-2 text-[13.5px] font-semibold text-ink-900"><FlaskConical className="h-4 w-4 text-ink-400" /> Counterfactual on v{data.to_version}</h3>
              <p className="mt-1 text-[12.5px] text-ink-500">What would the rule engine say about this exact version without one of its rules? Runs in memory; content, approvals and the rulebook are unchanged.</p>
              {ruleOptions.length === 0 ? (
                <p className="mt-2 text-[13px] italic text-ink-500">No rulebook findings on this version to test.</p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <select className={cx(inputCls, 'max-w-md')} value={ruleId} onChange={(e) => setRuleId(e.target.value)} aria-label="Rule to disable">
                    <option value="">Choose a rule to disable…</option>
                    {ruleOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                  </select>
                  <Button onClick={runCf} disabled={!ruleId}>Run counterfactual</Button>
                </div>
              )}
              {cf && (
                <p className="mt-3 text-[13px] text-ink-700">
                  Findings {cf.findings_before} → {cf.findings_after}.
                  {cf.policies_removed.length > 0 && <> No longer triggers: {cf.policies_removed.join(', ')}.</>}
                  {cf.policies_added.length > 0 && <> Would trigger: {cf.policies_added.join(', ')}.</>}
                  {cf.lost.length > 0 && <> Removed: {cf.lost.map((f) => `“${f.matched_text}”`).join(', ')}.</>}
                </p>
              )}
            </section>
          )}
        </div>

        <aside>
          <section className="rounded-xl border border-line bg-white">
            <h3 className="border-b border-line px-4 py-2.5 text-[13.5px] font-semibold text-ink-900">Timeline</h3>
            <ol className="relative max-h-[70vh] space-y-3 overflow-y-auto px-4 py-3">
              {data.timeline.map((e, i) => (
                <li key={i} className={cx('border-l-2 pl-3', e.version && (e.version === data.from_version || e.version === data.to_version) ? 'border-pine-500' : 'border-line')}>
                  <p className="text-[12px] text-ink-500">{formatDateTime(e.created_at)}{e.version ? ` · v${e.version}` : ''}</p>
                  <p className="text-[13px] text-ink-800"><span className="font-medium">{e.actor_name}</span> <span className="text-ink-500">({e.actor_role})</span></p>
                  <p className="text-[12.5px] leading-snug text-ink-600">{e.description}</p>
                </li>
              ))}
            </ol>
            <p className="border-t border-line px-4 py-2 text-[11.5px] text-ink-400">{data.integrity_note}</p>
          </section>
        </aside>
      </div>
    </Page>
  );
}
