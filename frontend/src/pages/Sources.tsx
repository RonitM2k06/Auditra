import { useCallback, useEffect, useRef, useState } from 'react';
import { FileText, Search, Trash2, Upload } from 'lucide-react';
import { Button, ClaimBadge, cx, EmptyState, Field, inputCls, Modal, Page, PageHeader, PageSkeleton, Section, useConfirm, useToast } from '../components/ui';
import type { Brand, ClaimCheck, SourceDoc, SourceDocDetail, WorkspaceRole } from '../types';
import { api } from '../api';

const today = new Date().toISOString().slice(0, 10);

function DateState({ d }: { d: SourceDoc }) {
  if (d.approval_status !== 'approved') return <span className="text-ink-500">{d.approval_status}: not used for verification</span>;
  if (d.expiry_date && d.expiry_date < today) return <span className="font-medium text-amber-800">expired {d.expiry_date}</span>;
  if (d.review_date && d.review_date < today) return <span className="font-medium text-amber-800">review overdue since {d.review_date}</span>;
  return <span className="text-pine-700">in force{d.expiry_date ? ` until ${d.expiry_date}` : ' · no expiry supplied'}</span>;
}

export function Sources({ brand, role, docId, navigate }: { brand: Brand; role: WorkspaceRole; docId: string | null; navigate: (p: string, id?: string | null) => void }) {
  const toast = useToast();
  const confirm = useConfirm();
  const isAdmin = role === 'admin';
  const [docs, setDocs] = useState<SourceDoc[] | null>(null);
  const [detail, setDetail] = useState<SourceDocDetail | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [meta, setMeta] = useState({ name: '', source_identifier: '', effective_date: '', expiry_date: '', review_date: '', approval_status: 'approved' });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [probe, setProbe] = useState('Atlas Pro costs $59 per member per month. Northstar maintains a 99.995% uptime SLA.');
  const [probeResult, setProbeResult] = useState<ClaimCheck[] | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => api.getSources(brand.id).then(setDocs).catch((e) => toast(e.message, 'error')), [brand.id, toast]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!docId) return setDetail(null);
    api.getSource(brand.id, docId).then(setDetail).catch((e) => toast(e.message, 'error'));
  }, [brand.id, docId, toast]);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const d = await api.uploadSource(brand.id, file, meta);
      toast(`Added “${d.name}” (${d.passage_count} passages).`, 'success');
      setUploadOpen(false);
      setFile(null);
      setMeta({ name: '', source_identifier: '', effective_date: '', expiry_date: '', review_date: '', approval_status: 'approved' });
      load();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    try {
      setProbeResult(await api.verifyText(brand.id, probe));
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (!docs) return <PageSkeleton />;

  return (
    <Page>
      <PageHeader
        title="Evidence library"
        description="Approved source documents that claims are checked against. Passages are stored verbatim and cited by ID; dates are only used when you supply them."
        actions={isAdmin && <Button variant="primary" onClick={() => setUploadOpen(true)}><Upload className="h-4 w-4" /> Add source</Button>}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div>
          {docs.length === 0 ? (
            <EmptyState title="No sources yet" body="Add product fact sheets, pricing sheets or policy documents (.txt, .md or text-based PDF). Until then, every claim is reported as having no evidence." />
          ) : (
            <ul className="space-y-2">
              {docs.map((d) => (
                <li key={d.id}>
                  <button
                    onClick={() => navigate('sources', d.id)}
                    className={cx('w-full rounded-lg border bg-white px-4 py-3 text-left transition-colors hover:border-ink-300', docId === d.id ? 'border-pine-500 ring-1 ring-pine-500' : 'border-line')}
                  >
                    <p className="flex items-center gap-2 text-[14px] font-medium text-ink-900"><FileText className="h-4 w-4 text-ink-400" />{d.name}</p>
                    <p className="mt-1 text-[12.5px] text-ink-500">
                      {d.source_identifier ?? 'no identifier'} · {d.file_format.toUpperCase()} · {d.passage_count} passages · <DateState d={d} />
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <Section title="Try the verifier" description="Paste marketing copy. Nothing is saved.">
            <textarea className={inputCls} rows={3} value={probe} onChange={(e) => setProbe(e.target.value)} />
            <Button size="sm" className="mt-2" onClick={check} disabled={!probe.trim()}><Search className="h-3.5 w-3.5" /> Check claims</Button>
            {probeResult && (
              <ul className="mt-3 space-y-2">
                {probeResult.length === 0 && <li className="text-[13px] italic text-ink-500">No checkable claims found in that text.</li>}
                {probeResult.map((c, i) => (
                  <li key={i} className="rounded-lg border border-line bg-white p-3 text-[13px]">
                    <ClaimBadge status={c.status} />
                    <p className="mt-1 font-medium text-ink-900">“{c.claim_text}”</p>
                    <p className="mt-1 text-ink-600">{c.rationale}</p>
                    {c.source && <button onClick={() => navigate('sources', c.source!.document_id)} className="mt-1 text-[12px] font-medium text-pine-700 hover:underline">{c.source.name}{c.source.section ? ` § ${c.source.section}` : ''}</button>}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div>
          {!detail ? (
            <div className="rounded-lg border border-dashed border-line px-6 py-16 text-center text-[13px] text-ink-500">Select a source to read its passages and metadata.</div>
          ) : (
            <article className="rounded-lg border border-line bg-white">
              <header className="border-b border-line px-5 py-4">
                <h2 className="text-[16px] font-semibold text-ink-900">{detail.name}</h2>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[12.5px] sm:grid-cols-3">
                  {[
                    ['Identifier', detail.source_identifier],
                    ['Status', detail.approval_status],
                    ['Effective', detail.effective_date],
                    ['Expires', detail.expiry_date],
                    ['Review by', detail.review_date],
                    ['Uploaded by', detail.uploaded_by],
                  ].map(([k, v]) => (
                    <div key={k as string}><dt className="text-ink-400">{k}</dt><dd className={cx(v ? 'text-ink-800' : 'italic text-ink-400')}>{v || 'not supplied'}</dd></div>
                  ))}
                </dl>
                <p className="mt-2 truncate font-mono text-[11px] text-ink-400" title={detail.sha256}>sha256 {detail.sha256}</p>
                {isAdmin && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(['approved', 'pending', 'retired'] as const).filter((s) => s !== detail.approval_status).map((s) => (
                      <Button key={s} size="sm" onClick={async () => {
                        try {
                          await api.updateSource(brand.id, detail.id, { approval_status: s });
                          setDetail({ ...detail, approval_status: s });
                          load();
                          toast(`Marked ${s}.`, 'success');
                        } catch (e: any) {
                          toast(e.message, 'error');
                        }
                      }}>Mark {s}</Button>
                    ))}
                    <Button size="sm" variant="danger" onClick={async () => {
                      if (await confirm({ title: `Delete “${detail.name}”?`, body: 'Past claim checks keep their copy of the cited passage. Future checks will not use this source.', confirmLabel: 'Delete', danger: true })) {
                        await api.deleteSource(brand.id, detail.id).catch((e) => toast(e.message, 'error'));
                        navigate('sources');
                        load();
                      }
                    }}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
                  </div>
                )}
              </header>
              <ol className="divide-y divide-line">
                {detail.passages.map((p) => (
                  <li key={p.id} id={`passage-${p.id}`} className="px-5 py-3">
                    <p className="text-[11px] uppercase tracking-wider text-ink-400">¶{p.ordinal + 1}{p.section ? ` · ${p.section}` : ''}{p.page ? ` · page ${p.page}` : ''}</p>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-ink-800">{p.text}</p>
                  </li>
                ))}
              </ol>
            </article>
          )}
        </div>
      </div>

      <Modal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Add an evidence source"
        description="UTF-8 .txt, Markdown or text-based PDF, up to 2 MB. Leave dates empty if the document does not state them."
        footer={<><Button onClick={() => setUploadOpen(false)}>Cancel</Button><Button variant="primary" onClick={upload} disabled={!file || busy}>{busy ? 'Uploading…' : 'Add source'}</Button></>}
      >
        <div className="space-y-3">
          <input ref={fileRef} type="file" accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-[13px]" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Name"><input className={inputCls} value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} placeholder={file?.name} /></Field>
            <Field label="Source identifier"><input className={inputCls} value={meta.source_identifier} onChange={(e) => setMeta({ ...meta, source_identifier: e.target.value })} /></Field>
            <Field label="Effective date"><input type="date" className={inputCls} value={meta.effective_date} onChange={(e) => setMeta({ ...meta, effective_date: e.target.value })} /></Field>
            <Field label="Expiry date"><input type="date" className={inputCls} value={meta.expiry_date} onChange={(e) => setMeta({ ...meta, expiry_date: e.target.value })} /></Field>
            <Field label="Review date"><input type="date" className={inputCls} value={meta.review_date} onChange={(e) => setMeta({ ...meta, review_date: e.target.value })} /></Field>
            <Field label="Status">
              <select className={inputCls} value={meta.approval_status} onChange={(e) => setMeta({ ...meta, approval_status: e.target.value })}>
                <option value="approved">Approved (used for verification)</option>
                <option value="pending">Pending (not used yet)</option>
              </select>
            </Field>
          </div>
        </div>
      </Modal>
    </Page>
  );
}
