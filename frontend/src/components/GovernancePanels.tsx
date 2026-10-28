import { useState } from 'react';
import { CheckCircle2, CircleDashed, Download, FileText, Send, ShieldAlert, ShieldCheck } from 'lucide-react';
import { Button, CLAIM_META, ClaimBadge, cx, formatDateTime } from './ui';
import type { ClaimCheck, ContentItemDetail } from '../types';
import { api } from '../api';

const ORDER = ['contradicted', 'stale', 'needs_review', 'unsupported', 'supported'];

export function ClaimsPanel({ checks, stale, onSelect, onOpenSource }: {
  checks: ClaimCheck[];
  stale: boolean;
  onSelect?: (c: ClaimCheck) => void;
  onOpenSource: (docId: string) => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  if (!checks.length) {
    return (
      <div className="px-6 py-10 text-center text-[13px] text-ink-500">
        <p className="font-medium text-ink-800">No checkable claims found</p>
        <p className="mx-auto mt-1 max-w-[32ch] leading-relaxed">Sentences with figures, superlatives or capability statements are checked against the approved sources after each analysis.</p>
      </div>
    );
  }
  const sorted = [...checks].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  const counts = ORDER.map((s) => [s, checks.filter((c) => c.status === s).length] as const).filter(([, n]) => n);
  return (
    <div>
      <div className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          {counts.map(([s, n]) => (
            <span key={s} className="flex items-center gap-1 text-[12px] text-ink-600"><ClaimBadge status={s} /> {n}</span>
          ))}
        </div>
        <p className="mt-2 text-[12px] leading-snug text-ink-500">
          Matched by BM25 retrieval over approved sources, then checked for the same figures, wording and dates. A matching passage is evidence for a reviewer, not proof.
        </p>
        {stale && <p className="mt-2 text-[12px] font-medium text-amber-800">These checks are from an earlier version. Re-run the analysis.</p>}
      </div>
      <ul>
        {sorted.map((c, i) => {
          const isOpen = open === i;
          const d = c.details || {};
          return (
            <li key={i} className={cx('border-b border-line', isOpen && 'bg-ink-50/60')}>
              <button onClick={() => { setOpen(isOpen ? null : i); onSelect?.(c); }} className="w-full px-4 py-3 text-left hover:bg-ink-50" aria-expanded={isOpen}>
                <ClaimBadge status={c.status} />
                <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-ink-900">“{c.claim_text}”</p>
              </button>
              {isOpen && (
                <div className="space-y-3 px-4 pb-4 text-[13px]">
                  <p className="leading-relaxed text-ink-700">{c.rationale}</p>
                  {c.passage_text && c.source ? (
                    <figure className="rounded-lg border border-line bg-white">
                      <blockquote className="border-l-[3px] border-pine-500 px-3 py-2.5 text-[13px] leading-relaxed text-ink-800">“{c.passage_text}”</blockquote>
                      <figcaption className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-3 py-2 text-[12px] text-ink-500">
                        <button onClick={() => onOpenSource(c.source!.document_id)} className="flex items-center gap-1 font-medium text-pine-700 hover:underline">
                          <FileText className="h-3.5 w-3.5" />{c.source.name}
                        </button>
                        {c.source.section && <span>§ {c.source.section}</span>}
                        {c.source.page && <span>p. {c.source.page}</span>}
                        <span>{c.source.effective_date ? `effective ${c.source.effective_date}` : 'no effective date supplied'}</span>
                        <span className={cx(c.source.expiry_date && c.source.expiry_date < new Date().toISOString().slice(0, 10) && 'font-medium text-amber-800')}>
                          {c.source.expiry_date ? `expires ${c.source.expiry_date}` : 'no expiry supplied'}
                        </span>
                        {c.source.review_date && <span>review by {c.source.review_date}</span>}
                      </figcaption>
                    </figure>
                  ) : (
                    <p className="rounded-md border border-dashed border-line px-3 py-2 text-[12.5px] italic text-ink-500">No source passage is cited.</p>
                  )}
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[12px] text-ink-600">
                    <dt className="text-ink-400">Term coverage</dt><dd className="tabular-nums">{Math.round(c.coverage * 100)}%</dd>
                    <dt className="text-ink-400">Retrieval score</dt><dd className="tabular-nums">{c.retrieval_score.toFixed(2)} (BM25)</dd>
                    {d.matched_quantities?.length > 0 && <><dt className="text-ink-400">Figures matched</dt><dd>{d.matched_quantities.join(', ')}</dd></>}
                    {d.conflicting_quantities?.length > 0 && <><dt className="text-ink-400">Figures differ</dt><dd className="text-red-700">{d.conflicting_quantities.map((q: any) => `${q.claim} vs ${q.source.join('/')}`).join('; ')}</dd></>}
                    {d.missing_quantities?.length > 0 && <><dt className="text-ink-400">Not in source</dt><dd>{d.missing_quantities.join(', ')}</dd></>}
                    {d.unbacked_absolute_terms?.length > 0 && <><dt className="text-ink-400">Unbacked absolutes</dt><dd>{d.unbacked_absolute_terms.join(', ')}</dd></>}
                    {d.expired_support && <><dt className="text-ink-400">Expired support</dt><dd>{d.expired_support}</dd></>}
                  </dl>
                  <p className="text-[11.5px] text-ink-400">{CLAIM_META[c.status]?.hint}</p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ApprovalPanel({ item, canPublish, onPublished, toast }: {
  item: ContentItemDetail;
  canPublish: boolean;
  onPublished: () => void;
  toast: (m: string, t?: 'success' | 'error' | 'info') => void;
}) {
  const [busy, setBusy] = useState(false);
  const st = item.approval_status;
  const publishedCurrent = item.publications.find((p) => p.version_number === item.current_version_number);
  const approvedCurrent = item.status === 'approved' && item.approved_version_id === item.current_version?.id;

  const publish = async () => {
    setBusy(true);
    try {
      const p = await api.publish(item.id, item.current_version_number);
      toast(p.duplicate ? `v${p.version_number} was already published; no duplicate was created.` : `Published v${p.version_number} to the sandbox.`, 'success');
      onPublished();
    } catch (e: any) {
      toast(e.message, 'error');
      onPublished();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5 px-4 py-4 text-[13px]">
      <section>
        <div className="flex items-center gap-2">
          {st?.satisfied ? <ShieldCheck className="h-5 w-5 text-pine-600" /> : <ShieldAlert className="h-5 w-5 text-amber-600" />}
          <h3 className="text-[14px] font-semibold text-ink-900">Approval requirements for v{item.current_version_number}</h3>
        </div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-ink-500">
          Evaluated on the server from this version’s open findings and claim checks. Approvals on earlier versions never count.
        </p>
        {!st?.reviewed && <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">This version has not been analysed, so it cannot be approved yet.</p>}
        <ul className="mt-3 space-y-2">
          {st?.requirements.map((r, i) => (
            <li key={i} className={cx('rounded-lg border px-3 py-2.5', r.met ? 'border-pine-200 bg-pine-50/50' : 'border-line bg-white')}>
              <p className="flex items-start gap-2 font-medium text-ink-900">
                {r.met ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-pine-600" /> : <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />}
                {r.name}
              </p>
              {r.trigger && <p className="ml-6 mt-0.5 text-[12px] text-ink-500">Triggered by {r.trigger}{r.reasons.length ? `: ${r.reasons.slice(0, 2).join('; ')}` : ''}</p>}
              {!r.met && r.missing.length > 0 && <p className="ml-6 mt-1 text-[12px] font-medium text-amber-800">{r.missing.join('; ')}</p>}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">Approvals on this version</h4>
        {st?.approvals.length ? (
          <ul className="mt-2 space-y-1">
            {st.approvals.map((a, i) => (
              <li key={i} className="flex items-center justify-between gap-2 text-[12.5px]">
                <span className="text-ink-800">{a.reviewer_name} <span className="text-ink-500">· {a.role}</span></span>
                <span className="text-ink-500">{a.evidence_confirmed ? 'evidence confirmed · ' : ''}{formatDateTime(a.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1.5 text-[12.5px] italic text-ink-500">None yet.</p>
        )}
      </section>

      <section className="rounded-xl border border-line bg-white p-3.5">
        <div className="flex items-center gap-2">
          <Send className="h-4 w-4 text-ink-500" />
          <h4 className="text-[13.5px] font-semibold text-ink-900">Publish</h4>
          <span className="ml-auto rounded bg-ink-100 px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-ink-500">Local sandbox</span>
        </div>
        <p className="mt-1 text-[12px] leading-snug text-ink-500">
          Writes a signed-off export record (content, SHA-256, approvals). Nothing is sent to a third-party channel. The server refuses drafts, rejected or stale versions and repeated requests.
        </p>
        {publishedCurrent ? (
          <p className="mt-2.5 text-[12.5px] font-medium text-pine-700">v{publishedCurrent.version_number} published by {publishedCurrent.published_by} · {formatDateTime(publishedCurrent.created_at)}</p>
        ) : (
          <Button size="sm" variant="primary" className="mt-2.5" onClick={publish} disabled={busy || !canPublish}
            title={!canPublish ? 'Only reviewers and admins can publish' : !approvedCurrent ? 'Try it: the server will refuse and log the attempt' : undefined}>
            {busy ? 'Publishing…' : `Publish v${item.current_version_number}`}
          </Button>
        )}
        {!approvedCurrent && !publishedCurrent && canPublish && (
          <p className="mt-1.5 text-[11.5px] text-ink-500">This version is not approved, so a publish attempt will be refused and recorded in the audit trail.</p>
        )}
        {item.publications.length > 0 && (
          <ul className="mt-3 space-y-1 border-t border-line pt-2.5">
            {item.publications.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-2 text-[12px]">
                <span className="truncate font-mono text-ink-600" title={p.destination}>v{p.version_number} → {p.destination}</span>
                <a href={api.exportUrl(p.id)} className="flex shrink-0 items-center gap-1 text-pine-700 hover:underline"><Download className="h-3 w-3" />Export</a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
