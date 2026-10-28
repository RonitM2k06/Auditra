import { useCallback, useEffect, useState } from 'react';
import { FileWarning, ImageUp, Sparkles, Wand2 } from 'lucide-react';
import { Button, CATEGORY_LABEL, ClaimBadge, cx, Modal, SeverityTag } from './ui';
import type { ContentItemDetail } from '../types';
import { api } from '../api';

export interface Suggestion {
  id: string;
  kind: 'wording' | 'add_disclosure' | 'factual' | 'evidence_needed' | 'creative' | 'manual';
  severity: string;
  category: string;
  original: string;
  replacement: string | null;
  note: string;
  explanation: string;
  requires_confirmation?: boolean;
  evidence?: { passage: string | null; source: string | null; section: string | null; expiry_date: string | null };
}

export interface RemediationPreview {
  before_body: string;
  after_body: string;
  diff: Array<{ op: 'equal' | 'insert' | 'delete'; text: string }>;
  findings_before: number;
  findings_after: number;
  resolved: Array<{ category: string; matched_text: string }>;
  introduced: Array<{ category: string; matched_text: string; severity: string }>;
  claims_after: Array<{ claim_text: string; status: string; was: string | null; source: string | null }>;
  factual_changes: string[];
  note: string;
}

const KIND_LABEL: Record<string, string> = {
  wording: 'Approved wording',
  add_disclosure: 'Add disclosure',
  factual: 'Factual change',
  evidence_needed: 'Evidence needed',
  creative: 'Revise creative',
  manual: 'Rewrite needed',
};
const FIXABLE = new Set(['wording', 'add_disclosure', 'factual', 'manual']);

export function RemediationPanel({ item, canEdit, onApplied, toast }: {
  item: ContentItemDetail;
  canEdit: boolean;
  onApplied: (d: ContentItemDetail) => void;
  toast: (m: string, t?: 'success' | 'error' | 'info') => void;
}) {
  const [data, setData] = useState<{ analysed: boolean; suggestions: Suggestion[]; notice: string | null } | null>(null);
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<RemediationPreview | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.getRemediation(item.id).then((d) => { setData(d); setPicked({}); }).catch((e) => toast(e.message, 'error'));
  }, [item.id, toast]);
  useEffect(() => {
    load();
  }, [load, item.current_version_number, item.latest_review?.id]);

  const fixes = () => Object.entries(picked).map(([id, replacement]) => {
    const s = data!.suggestions.find((x) => x.id === id)!;
    return s.kind === 'add_disclosure' ? { id } : { id, replacement };
  });

  const runPreview = async () => {
    setBusy(true);
    try {
      setPreview(await api.previewRemediation(item.id, item.current_version_number, fixes()));
      setConfirm(false);
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    setBusy(true);
    try {
      const d = await api.applyRemediation(item.id, item.current_version_number, fixes(), confirm);
      toast(`Saved as v${d.current_version_number}. Approval reset — run the analysis, then submit for review.`, 'success');
      setPreview(null);
      onApplied(d);
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <p className="px-6 py-10 text-center text-[13px] text-ink-500">Loading suggestions…</p>;
  if (!data.analysed) return <p className="px-6 py-10 text-center text-[13px] text-ink-500">{data.notice}</p>;
  if (!data.suggestions.length) return <p className="px-6 py-10 text-center text-[13px] text-ink-500">Nothing to fix on this version.</p>;

  const count = Object.keys(picked).length;
  return (
    <div>
      <div className="border-b border-line px-4 py-3 text-[12.5px] leading-snug text-ink-600">
        <p className="flex items-center gap-1.5 font-medium text-ink-900"><Wand2 className="h-4 w-4 text-pine-600" /> Remediation workbench</p>
        <p className="mt-1">Suggestions are <b>not approved content</b>. Pick fixes, preview the before/after with every check re-run, then apply as a new version. Figures and dates are only changed with your confirmation and a cited source.</p>
      </div>
      <ul>
        {data.suggestions.map((s) => {
          const fixable = canEdit && FIXABLE.has(s.kind);
          const on = s.id in picked;
          return (
            <li key={s.id} className={cx('border-b border-line px-4 py-3', on && 'bg-pine-50/40')}>
              <label className={cx('flex items-start gap-2.5', fixable ? 'cursor-pointer' : 'cursor-default')}>
                <input type="checkbox" className="mt-1 accent-pine-600" disabled={!fixable} checked={on}
                  onChange={(e) => setPicked((p) => {
                    const n = { ...p };
                    if (e.target.checked) n[s.id] = s.replacement ?? '';
                    else delete n[s.id];
                    return n;
                  })} aria-label={`Select fix for ${s.original || CATEGORY_LABEL[s.category]}`} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5 text-[12px]">
                    {s.category.startsWith('claim_') ? <ClaimBadge status={s.category.replace('claim_', '')} /> : <SeverityTag severity={s.severity} />}
                    <span className={cx('rounded px-1.5 py-px font-medium',
                      s.kind === 'factual' ? 'bg-amber-100 text-amber-900' : s.kind === 'evidence_needed' ? 'bg-ink-100 text-ink-700' : 'bg-pine-50 text-pine-700')}>
                      {KIND_LABEL[s.kind]}
                    </span>
                  </span>
                  {s.original && <span className="mt-1 block text-[13px] text-ink-900 line-through decoration-red-400/70">{s.original}</span>}
                  {s.kind === 'evidence_needed' && <span className="mt-1 flex items-start gap-1 text-[12.5px] text-ink-600"><FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" />{s.note}</span>}
                  {s.kind === 'creative' && <span className="mt-1 flex items-start gap-1 text-[12.5px] text-ink-600"><ImageUp className="mt-0.5 h-3.5 w-3.5 shrink-0" />{s.note}{s.replacement ? ` Suggested wording: “${s.replacement}”.` : ''}</span>}
                </span>
              </label>
              {on && s.kind !== 'add_disclosure' && (
                <textarea rows={2} value={picked[s.id]} onChange={(e) => setPicked((p) => ({ ...p, [s.id]: e.target.value }))}
                  className="ml-6 mt-2 w-[calc(100%-1.5rem)] rounded-md border border-line px-2 py-1.5 text-[13px] focus:border-pine-500 focus:outline-none"
                  aria-label="Replacement text" placeholder="Write the replacement…" />
              )}
              {on && s.kind === 'add_disclosure' && <p className="ml-6 mt-1.5 rounded bg-white px-2 py-1 text-[12.5px] text-pine-800">+ {s.replacement}</p>}
              {FIXABLE.has(s.kind) && <p className="ml-6 mt-1 text-[11.5px] text-ink-500">{s.note}</p>}
              {s.evidence?.passage && (
                <p className="ml-6 mt-1 border-l-2 border-pine-400 pl-2 text-[12px] text-ink-600">“{s.evidence.passage}” — {s.evidence.source}{s.evidence.section ? ` § ${s.evidence.section}` : ''}</p>
              )}
            </li>
          );
        })}
      </ul>
      {canEdit && (
        <div className="sticky bottom-0 flex items-center gap-2 border-t border-line bg-white px-4 py-3">
          <span className="text-[12.5px] text-ink-600">{count} selected</span>
          <Button size="sm" variant="primary" className="ml-auto" disabled={!count || busy} onClick={runPreview}>
            <Sparkles className="h-3.5 w-3.5" /> {busy && !preview ? 'Checking…' : 'Preview fixes'}
          </Button>
        </div>
      )}

      <Modal open={!!preview} onClose={() => setPreview(null)} width="max-w-3xl" title="Preview: before and after"
        description={preview?.note}
        footer={<>
          <Button onClick={() => setPreview(null)}>Keep editing</Button>
          <Button variant="primary" disabled={busy || (!!preview?.factual_changes.length && !confirm)} onClick={apply}>
            {busy ? 'Saving…' : `Apply as v${item.current_version_number + 1}`}
          </Button>
        </>}>
        {preview && (
          <div className="space-y-4 text-[13px]">
            <div className="max-h-60 overflow-y-auto whitespace-pre-wrap rounded-md border border-line bg-paper px-3 py-2.5 leading-relaxed text-ink-900">
              {preview.diff.map((d, i) => d.op === 'equal' ? <span key={i}>{d.text}</span>
                : d.op === 'insert' ? <ins key={i} className="rounded-sm bg-pine-100 text-pine-800 no-underline">{d.text}</ins>
                : <del key={i} className="rounded-sm bg-red-50 text-red-700">{d.text}</del>)}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-line p-3">
                <p className="font-medium text-ink-900">Rule findings {preview.findings_before} → {preview.findings_after}</p>
                {preview.resolved.map((f, i) => <p key={i} className="text-pine-700">✓ {CATEGORY_LABEL[f.category] ?? f.category}: {f.matched_text}</p>)}
                {preview.introduced.map((f, i) => <p key={i} className="text-red-700">+ {CATEGORY_LABEL[f.category] ?? f.category}: {f.matched_text}</p>)}
              </div>
              <div className="rounded-md border border-line p-3">
                <p className="font-medium text-ink-900">Claims after the fix</p>
                {preview.claims_after.length === 0 && <p className="text-ink-500">No checkable claims.</p>}
                {preview.claims_after.map((c, i) => (
                  <p key={i} className="mt-1 flex items-start gap-1.5"><ClaimBadge status={c.status} /><span className="text-ink-700">{c.claim_text}</span></p>
                ))}
              </div>
            </div>
            {preview.factual_changes.length > 0 && (
              <label className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2.5 text-amber-900">
                <input type="checkbox" className="mt-0.5 accent-amber-600" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
                <span>This changes factual figures or dates ({preview.factual_changes.join(', ')}). I confirmed the new values against the cited source.</span>
              </label>
            )}
            <p className="text-[12px] text-ink-500">Applying keeps every earlier version, resets any approval, and the new version must be analysed and approved before it can be published.</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
