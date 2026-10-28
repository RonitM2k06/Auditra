import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { Button, CONTENT_TYPES, cx, EmptyState, Field, inputCls, Modal, Page, PageHeader, PageSkeleton, StatusPill, useConfirm, useToast } from '../components/ui';
import type { Brand, Campaign, CampaignIssue, Consistency, ContentItem, FactGroup } from '../types';
import { api } from '../api';

const STATUS_COLOR: Record<string, string> = { consistent: '#0F9488', confirmed_mismatch: '#DC2626', uncertain: '#F59E0B' };
const ISSUE_META: Record<string, { label: string; cls: string }> = {
  confirmed_mismatch: { label: 'Confirmed mismatch', cls: 'bg-red-50 text-red-700 border-red-200' },
  uncertain: { label: 'Uncertain match', cls: 'bg-amber-50 text-amber-800 border-amber-200' },
  missing_information: { label: 'Missing information', cls: 'bg-orange-50 text-orange-800 border-orange-200' },
  rule_conflict: { label: 'Rule conflict', cls: 'bg-ink-100 text-ink-700 border-line' },
};

function Highlight({ text, value }: { text: string; value: string }) {
  const i = text.indexOf(value);
  if (i < 0) return <>{text}</>;
  return <>{text.slice(0, i)}<mark className="rounded-sm bg-amber-100 px-0.5 font-medium text-ink-900">{value}</mark>{text.slice(i + value.length)}</>;
}

/** Bipartite view: assets on the left, extracted facts on the right; edges coloured by agreement. */
function ConsistencyGraph({ data, focus, onFocus }: { data: Consistency; focus: string | null; onFocus: (id: string | null) => void }) {
  const assets = [...(data.brief ? [{ content_id: 'brief', title: 'Approved brief', content_type: 'brief' }] : []), ...data.assets];
  const facts = data.facts;
  const rowH = 58;
  const h = Math.max(assets.length, facts.length) * rowH + 44;
  const W = 760;
  const ay = (i: number) => 52 + i * rowH + (Math.max(0, facts.length - assets.length) * rowH) / 2;
  const fy = (i: number) => 52 + i * rowH + (Math.max(0, assets.length - facts.length) * rowH) / 2;
  const aIndex = Object.fromEntries(assets.map((a, i) => [a.content_id, i]));
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white">
      <svg viewBox={`0 0 ${W} ${h}`} className="w-full min-w-[640px]" role="img" aria-label="Campaign consistency graph">
        <text x={20} y={16} className="fill-ink-400 text-[11px] uppercase tracking-wider">Assets</text>
        <text x={W - 250} y={16} className="fill-ink-400 text-[11px] uppercase tracking-wider">Extracted facts</text>
        {facts.map((f, fi) =>
          f.members.map((m, mi) => {
            const ai = aIndex[m.asset_id];
            if (ai === undefined) return null;
            const dim = focus && focus !== f.id;
            const x1 = 230, y1 = ay(ai), x2 = W - 260, y2 = fy(fi);
            return (
              <g key={`${f.id}-${mi}`} opacity={dim ? 0.15 : 1}>
                <path d={`M${x1},${y1} C${x1 + 120},${y1} ${x2 - 120},${y2} ${x2},${y2}`} fill="none" stroke={STATUS_COLOR[f.status]} strokeWidth={f.status === 'consistent' ? 1.5 : 2.5} />
              </g>
            );
          }),
        )}
        {assets.map((a, i) => (
          <g key={a.content_id}>
            <rect x={12} y={ay(i) - 20} width={218} height={40} rx={8} className={a.content_id === 'brief' ? 'fill-navy-900' : 'fill-white'} stroke="#D0D5DD" />
            <text x={24} y={ay(i) - 3} className={cx('text-[12px] font-medium', a.content_id === 'brief' ? 'fill-white' : 'fill-ink-900')}>{a.title.length > 30 ? `${a.title.slice(0, 29)}…` : a.title}</text>
            <text x={24} y={ay(i) + 12} className={cx('text-[10.5px]', a.content_id === 'brief' ? 'fill-slate-300' : 'fill-ink-500')}>{CONTENT_TYPES[a.content_type] ?? a.content_type}</text>
          </g>
        ))}
        {facts.map((f, i) => (
          <g key={f.id} className="cursor-pointer" onClick={() => onFocus(focus === f.id ? null : f.id)}>
            <rect x={W - 260} y={fy(i) - 20} width={248} height={40} rx={8} fill="#fff" stroke={STATUS_COLOR[f.status]} strokeWidth={focus === f.id ? 2.5 : 1.5} />
            <circle cx={W - 246} cy={fy(i)} r={4} fill={STATUS_COLOR[f.status]} />
            <text x={W - 236} y={fy(i) - 3} className="fill-ink-900 text-[12px] font-medium">{f.label.length > 30 ? `${f.label.slice(0, 29)}…` : f.label}</text>
            <text x={W - 236} y={fy(i) + 12} className="fill-ink-500 text-[10.5px]">{f.status.replace('_', ' ')} · {Array.from(new Set(f.members.map((m) => m.display))).join(' vs ').slice(0, 34)}</text>
          </g>
        ))}
      </svg>
      <div className="flex flex-wrap gap-4 border-t border-line px-4 py-2 text-[12px] text-ink-600">
        {Object.entries(STATUS_COLOR).map(([k, c]) => <span key={k} className="flex items-center gap-1.5"><span className="h-0.5 w-5" style={{ background: c }} />{k.replace('_', ' ')}</span>)}
        <span className="ml-auto text-ink-400">Click a fact to focus it</span>
      </div>
    </div>
  );
}

export function Campaigns({ brand, canManage, campaignId: routeId, navigate }: { brand: Brand; canManage: boolean; campaignId: string | null; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [data, setData] = useState<Consistency | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [items, setItems] = useState<ContentItem[]>([]);
  const campaignId = routeId ?? campaigns?.[0]?.id ?? null;
  const [editor, setEditor] = useState<null | { id?: string; name: string; brief: string; content_ids: string[] }>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.getCampaigns(brand.id);
      setCampaigns(list);
    } catch (e: any) {
      toast(e.message, 'error');
    }
  }, [brand.id, toast]);

  useEffect(() => {
    load();
    api.getContentItems(brand.id).then(setItems).catch(() => undefined);
  }, [load, brand.id]);

  useEffect(() => {
    setData(null);
    setFocus(null);
    if (campaignId) api.getConsistency(campaignId).then(setData).catch((e) => toast(e.message, 'error'));
  }, [campaignId, toast]);

  const title = useMemo(() => Object.fromEntries([['brief', 'Approved brief'], ...(data?.assets ?? []).map((a) => [a.content_id, a.title])]), [data]);

  const save = async () => {
    if (!editor) return;
    try {
      const c = editor.id ? await api.updateCampaign(editor.id, editor) : await api.createCampaign(brand.id, editor);
      setEditor(null);
      toast('Campaign saved.', 'success');
      await load();
      navigate('campaigns', c.id);
      setData(await api.getConsistency(c.id));
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (!campaigns) return <PageSkeleton />;

  const factById = Object.fromEntries((data?.facts ?? []).map((f) => [f.id, f])) as Record<string, FactGroup>;
  const issueOrder = ['confirmed_mismatch', 'missing_information', 'rule_conflict', 'uncertain'];
  const issues = [...(data?.issues ?? [])].sort((a, b) => issueOrder.indexOf(a.kind) - issueOrder.indexOf(b.kind));

  return (
    <Page width="max-w-7xl">
      <PageHeader
        title="Campaign consistency"
        description="Compares prices, dates, quantities and required disclosures across every asset in a campaign, and against its approved brief. Values are only compared when the surrounding wording refers to the same thing."
        actions={canManage && <Button variant="primary" onClick={() => setEditor({ name: '', brief: '', content_ids: [] })}><Plus className="h-4 w-4" /> New campaign</Button>}
      />
      {campaigns.length === 0 ? (
        <EmptyState title="No campaigns yet" body="Group two or more pieces of content into a campaign to check that they agree with each other." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
          <nav className="space-y-1" aria-label="Campaigns">
            {campaigns.map((c) => (
              <button key={c.id} onClick={() => navigate('campaigns', c.id)} className={cx('w-full rounded-lg px-3 py-2 text-left text-[13.5px]', c.id === campaignId ? 'bg-white font-medium text-ink-900 shadow-sm ring-1 ring-line' : 'text-ink-600 hover:bg-white')}>
                {c.name}<span className="block text-[12px] font-normal text-ink-500">{c.assets.length} assets</span>
              </button>
            ))}
          </nav>
          <div className="min-w-0 space-y-6">
            {!data ? (
              <PageSkeleton />
            ) : (
              <>
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[18px] font-semibold text-ink-900">{data.name}</h2>
                    {data.brief && <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-ink-600"><span className="font-medium text-ink-800">Brief: </span>{data.brief}</p>}
                  </div>
                  {canManage && (
                    <>
                      <Button size="sm" onClick={() => setEditor({ id: data.id, name: data.name, brief: data.brief ?? '', content_ids: data.assets.map((a) => a.content_id) })}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
                      <Button size="sm" variant="danger" onClick={async () => {
                        if (await confirm({ title: `Delete “${data.name}”?`, body: 'Only the grouping is deleted. The content items stay.', confirmLabel: 'Delete', danger: true })) {
                          await api.deleteCampaign(data.id).catch((e) => toast(e.message, 'error'));
                          navigate('campaigns');
                          load();
                        }
                      }}><Trash2 className="h-3.5 w-3.5" /></Button>
                    </>
                  )}
                </div>

                {data.notice ? (
                  <EmptyState title="Not enough assets" body={data.notice} />
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                      {[['Confirmed mismatches', data.counts.confirmed_mismatch, 'text-red-700'], ['Missing info', data.counts.missing_information, 'text-orange-700'], ['Rule conflicts', data.counts.rule_conflict, 'text-ink-800'], ['Uncertain', data.counts.uncertain, 'text-amber-700'], ['Consistent facts', data.counts.consistent_facts, 'text-pine-700']].map(([l, n, c]) => (
                        <div key={l as string} className="rounded-xl border border-line bg-white px-3 py-2.5">
                          <p className={cx('text-[22px] font-semibold tabular-nums', (n as number) ? (c as string) : 'text-ink-300')}>{(n as number) ?? 0}</p>
                          <p className="text-[12px] text-ink-500">{l}</p>
                        </div>
                      ))}
                    </div>

                    {data.facts.length > 0 && <ConsistencyGraph data={data} focus={focus} onFocus={setFocus} />}

                    <section>
                      <h3 className="mb-2 text-[14px] font-semibold text-ink-900">Issues to resolve</h3>
                      {issues.length === 0 ? (
                        <p className="rounded-lg border border-line bg-white px-4 py-3 text-[13px] text-ink-600">No inconsistencies found across these assets.</p>
                      ) : (
                        <ul className="space-y-3">
                          {issues.map((iss: CampaignIssue, i) => {
                            const fact = iss.fact_id ? factById[iss.fact_id] : null;
                            return (
                              <li key={i} className="rounded-xl border border-line bg-white p-4" onMouseEnter={() => fact && setFocus(fact.id)}>
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className={cx('rounded border px-1.5 py-0.5 text-[11px] font-semibold', ISSUE_META[iss.kind].cls)}>{ISSUE_META[iss.kind].label}</span>
                                  <p className="text-[14px] font-medium text-ink-900">{iss.title}</p>
                                </div>
                                <p className="mt-1.5 text-[13px] leading-relaxed text-ink-700">{iss.explanation}</p>
                                {fact && (
                                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                                    {fact.members.map((m, k) => (
                                      <figure key={k} className="rounded-lg border border-line bg-paper px-3 py-2">
                                        <figcaption className="mb-1 flex items-center justify-between text-[11.5px] text-ink-500">
                                          <span className="font-medium text-ink-700">{title[m.asset_id] ?? m.asset_id}</span>
                                          {m.asset_id !== 'brief' && <button onClick={() => navigate('studio', m.asset_id)} className="text-pine-700 hover:underline">Open to fix</button>}
                                        </figcaption>
                                        <blockquote className="text-[13px] leading-relaxed text-ink-800"><Highlight text={m.passage} value={m.display} /></blockquote>
                                      </figure>
                                    ))}
                                  </div>
                                )}
                                {!fact && (
                                  <p className="mt-2 flex flex-wrap gap-2 text-[12.5px]">
                                    {iss.passage && <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-ink-900">“{iss.passage}”</span>}
                                    {iss.asset_ids.map((id) => <button key={id} onClick={() => navigate('studio', id)} className="rounded border border-line px-1.5 py-0.5 text-ink-700 hover:border-ink-400">{title[id] ?? id} →</button>)}
                                    {iss.source_reference && <span className="text-ink-500">{iss.source_reference}</span>}
                                  </p>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </section>

                    <section>
                      <h3 className="mb-2 text-[14px] font-semibold text-ink-900">Assets</h3>
                      <ul className="divide-y divide-line rounded-lg border border-line bg-white">
                        {data.assets.map((a) => (
                          <li key={a.content_id} className="flex items-center gap-3 px-4 py-2.5 text-[13px]">
                            <button onClick={() => navigate('studio', a.content_id)} className="min-w-0 flex-1 truncate text-left font-medium text-ink-900 hover:underline">{a.title}</button>
                            <span className="text-ink-500">{CONTENT_TYPES[a.content_type] ?? a.content_type}{a.media_kind === 'image' ? ' · image' : ''} · v{a.version_number}</span>
                            <StatusPill status={a.status} />
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-[12px] text-ink-500">Each asset’s current version is compared. Fixing an asset in the studio creates a new version; nothing is rewritten or published automatically.</p>
                    </section>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <Modal open={!!editor} onClose={() => setEditor(null)} title={editor?.id ? 'Edit campaign' : 'New campaign'} width="max-w-2xl"
        footer={<><Button onClick={() => setEditor(null)}>Cancel</Button><Button variant="primary" onClick={save} disabled={!editor || editor.name.trim().length < 2}>Save</Button></>}>
        {editor && (
          <div className="space-y-3">
            <Field label="Name" required><input className={inputCls} value={editor.name} onChange={(e) => setEditor({ ...editor, name: e.target.value })} /></Field>
            <Field label="Approved brief" hint="Optional. Used as the reference text that assets are compared with.">
              <textarea className={inputCls} rows={3} value={editor.brief} onChange={(e) => setEditor({ ...editor, brief: e.target.value })} />
            </Field>
            <p className="text-[13px] font-medium text-ink-800">Assets</p>
            <ul className="max-h-64 space-y-1 overflow-y-auto rounded-md border border-line p-2">
              {items.map((it) => (
                <li key={it.id}>
                  <label className="flex items-center gap-2 rounded px-2 py-1 text-[13px] hover:bg-ink-50">
                    <input type="checkbox" className="accent-pine-600" checked={editor.content_ids.includes(it.id)}
                      onChange={(e) => setEditor({ ...editor, content_ids: e.target.checked ? [...editor.content_ids, it.id] : editor.content_ids.filter((x) => x !== it.id) })} />
                    <span className="flex-1 truncate">{it.title}</span>
                    <span className="text-[12px] text-ink-400">{CONTENT_TYPES[it.content_type] ?? it.content_type}</span>
                  </label>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Modal>
    </Page>
  );
}
