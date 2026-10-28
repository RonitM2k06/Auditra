import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, BookOpen, Check, ChevronDown, CornerDownLeft, FileText, History as HistoryIcon, ImageUp, Pencil, RotateCcw } from 'lucide-react';
import {
  ACTORS,
  Button,
  CATEGORY_LABEL,
  CONTENT_TYPES,
  cx,
  Field,
  inputCls,
  Modal,
  SEV_META,
  SEVERITIES,
  SeverityTag,
  StatusPill,
  Tabs,
  formatDateTime,
  timeAgo,
  useConfirm,
  useToast,
  type Role,
} from '../components/ui';
import { DecisionModal, type Decision } from '../components/DecisionModal';
import { CreativeView } from '../components/CreativeView';
import { ApprovalPanel, ClaimsPanel } from '../components/GovernancePanels';
import type { Brand, ContentItemDetail, ContentVersion, Finding } from '../types';
import { api } from '../api';

const MAX_CHARS = 20000;
const SAMPLE_COPY =
  'Northstar guarantees results for every customer. Our users will double their performance in seven days. Join today and unlock the unbelievable secret to instant cloud speed!!!';

type Busy = null | 'save' | 'review' | 'apply' | 'submit' | 'decide' | 'comment';
type SourceFilter = 'all' | 'rule' | 'builtin' | 'ai';

function sourceOf(f: Finding): Exclude<SourceFilter, 'all'> {
  if (f.finding_source === 'ai_assisted') return 'ai';
  if (f.finding_source === 'visual' || f.finding_source === 'ocr' || f.finding_source === 'evidence') return 'builtin';
  return f.rule_id ? 'rule' : 'builtin';
}

const SOURCE_LABEL: Record<Exclude<SourceFilter, 'all'>, string> = {
  rule: 'Rulebook',
  builtin: 'Built-in check',
  ai: 'AI suggestion',
};

interface StudioProps {
  brand: Brand;
  contentId: string | null;
  role: Role;
  navigate: (page: string, id?: string | null, replace?: boolean) => void;
  onChanged: () => void;
}

export function Studio({ brand, contentId, role, navigate, onChanged }: StudioProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const actor = ACTORS[role];
  const canDecide = role !== 'creator';
  const canEdit = role !== 'reviewer';
  const canPublish = role !== 'creator';
  const reviseRef = useRef<HTMLInputElement>(null);

  const [item, setItem] = useState<ContentItemDetail | null>(null);
  const [title, setTitle] = useState('');
  const [type, setType] = useState('social_post');
  const [body, setBody] = useState('');
  const [saved, setSaved] = useState({ title: '', type: 'social_post', body: '' });
  const [loading, setLoading] = useState(!!contentId);
  const [busy, setBusy] = useState<Busy>(null);

  const [mode, setMode] = useState<'edit' | 'marked'>('edit');
  const [panel, setPanel] = useState<'findings' | 'claims' | 'approval' | 'history' | 'discussion'>('findings');
  const [sevFilter, setSevFilter] = useState<string>('all');
  const [srcFilter, setSrcFilter] = useState<SourceFilter>('all');
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const [chooser, setChooser] = useState<{ finding: Finding; custom?: string; positions: number[] } | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [comment, setComment] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hydrate = useCallback((d: ContentItemDetail) => {
    const text = d.current_version?.body ?? '';
    setItem(d);
    setTitle(d.title);
    setType(d.content_type);
    setBody(text);
    setSaved({ title: d.title, type: d.content_type, body: text });
  }, []);

  useEffect(() => {
    setSelected(null);
    setEditing(null);
    if (!contentId) {
      setItem(null);
      setTitle('');
      setType('social_post');
      setBody('');
      setSaved({ title: '', type: 'social_post', body: '' });
      setMode('edit');
      setLoading(false);
      return;
    }
    if (item?.id === contentId) return; // already hydrated (e.g. right after creation)
    setLoading(true);
    api
      .getContentItem(contentId)
      .then((d) => {
        hydrate(d);
        const fresh = d.latest_review && d.latest_review.content_version_id === d.current_version?.id;
        setMode(fresh ? 'marked' : 'edit');
      })
      .catch((e) => toast(e.message, 'error'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contentId]);

  /* ---------------- derived state ---------------- */
  const bodyDirty = body !== saved.body;
  const dirty = bodyDirty || title !== saved.title || type !== saved.type;
  const review = item?.latest_review ?? null;
  const reviewedVersion = item?.versions.find((v) => v.id === review?.content_version_id);
  const stale = !!review && (review.content_version_id !== item?.current_version?.id || bodyDirty);
  const findings = useMemo(() => (review?.findings ?? []).filter((f) => !f.is_dismissed), [review]);
  const openFindings = findings.filter((f) => !f.is_applied);
  const openSeverity = (s: string) => openFindings.filter((f) => f.severity === s).length;
  const visible = findings.filter((f) => (sevFilter === 'all' || f.severity === sevFilter) && (srcFilter === 'all' || sourceOf(f) === srcFilter));
  const effectiveMode = stale || !review ? 'edit' : mode;
  const words = body.trim() ? body.trim().split(/\s+/).length : 0;
  const status = item?.status ?? 'draft';
  const canSubmit = !!item && canEdit && ['draft', 'changes_requested', 'rejected'].includes(status);
  const isImage = item?.media_kind === 'image';
  const claimChecks = item?.claim_checks ?? [];
  const contradictedClaims = claimChecks.filter((c) => c.status === 'contradicted' || c.status === 'stale').length;
  const reload = async () => {
    if (item) hydrate(await api.getContentItem(item.id));
  };

  /* ---------------- actions ---------------- */
  const persist = async (): Promise<ContentItemDetail | null> => {
    if (!title.trim()) {
      toast('Give the piece a title first.', 'error');
      return null;
    }
    if (!body.trim()) {
      toast('There is no text to save yet.', 'error');
      return null;
    }
    if (body.length > MAX_CHARS) {
      toast(`Text is over the ${MAX_CHARS.toLocaleString()} character limit.`, 'error');
      return null;
    }
    if (!item) {
      const created = await api.createContentItem(brand.id, { title: title.trim(), content_type: type, body });
      hydrate(created);
      navigate('studio', created.id, true);
      return created;
    }
    if (!dirty) return item;
    const updated = await api.updateContentItem(item.id, {
      title: title.trim(),
      content_type: type,
      body: bodyDirty ? body : undefined,
      change_summary: 'Edited in the studio',
    });
    hydrate(updated);
    return updated;
  };

  const save = async () => {
    if (busy) return;
    setBusy('save');
    try {
      const d = await persist();
      if (d) toast(`Saved as v${d.current_version_number}.`, 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(null);
    }
  };

  const runReview = async () => {
    if (busy) return;
    setBusy('review');
    try {
      const d = isImage && item ? item : await persist();
      if (!d) return;
      const run = await api.runReview(d.id, {});
      const fresh = await api.getContentItem(d.id);
      hydrate(fresh);
      setMode('marked');
      const cc = fresh.claim_checks.filter((c) => c.status !== 'supported').length;
      if (cc) setTimeout(() => toast(`${cc} claim${cc === 1 ? '' : 's'} not fully supported by approved sources. See the Claims tab.`, 'info'), 400);
      setPanel('findings');
      setSelected(null);
      const n = run.findings.length;
      toast(n ? `${n} finding${n === 1 ? '' : 's'} on v${fresh.current_version_number}.` : `No issues found on v${fresh.current_version_number}.`, n ? 'info' : 'success');
      onChanged();
    } catch (e: any) {
      toast(`Review failed: ${e.message}. Your text is unchanged.`, 'error');
    } finally {
      setBusy(null);
    }
  };

  const apply = async (f: Finding, custom?: string, offset?: number) => {
    setBusy('apply');
    try {
      const d = await api.applyCorrection(f.id, { custom_replacement: custom, occurrence_offset: offset });
      hydrate(d);
      setEditing(null);
      setChooser(null);
      toast(`Applied. Saved as v${d.current_version_number}. Run the review again to confirm.`, 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(null);
    }
  };

  /** Resolve exactly which occurrence to change before calling the API. */
  const startApply = (f: Finding, custom?: string) => {
    if (bodyDirty) {
      toast('Save or discard your edits before applying a suggestion.', 'error');
      return;
    }
    if (f.category === 'required_phrase' || f.start_offset === f.end_offset) {
      apply(f, custom);
      return;
    }
    const target = f.matched_text;
    const positions: number[] = [];
    for (let i = body.indexOf(target); i !== -1; i = body.indexOf(target, i + 1)) positions.push(i);
    if (positions.length === 0) {
      toast('That text is no longer in the current version. Run the review again.', 'error');
      return;
    }
    if (!stale && body.slice(f.start_offset, f.end_offset) === target) return apply(f, custom, f.start_offset);
    if (positions.length === 1) return apply(f, custom, positions[0]);
    setChooser({ finding: f, custom, positions });
  };

  const dismiss = async (f: Finding) => {
    try {
      await api.dismissFinding(f.id);
      if (item) hydrate(await api.getContentItem(item.id));
      toast('Finding dismissed. This is recorded in the audit trail.', 'info');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const submit = async () => {
    if (!item || busy) return;
    if (dirty) {
      toast('Save your edits before submitting.', 'error');
      return;
    }
    const serious = openFindings.filter((f) => f.severity === 'critical' || f.severity === 'high').length;
    if (!review || stale) {
      const ok = await confirm({
        title: 'Submit without a current review?',
        body: 'This version hasn’t been checked against the rulebook. The reviewer will see it without up-to-date findings.',
        confirmLabel: 'Submit anyway',
      });
      if (!ok) return;
    } else if (serious > 0) {
      const ok = await confirm({
        title: 'Submit with open findings?',
        body: `${serious} critical or high finding${serious === 1 ? ' is' : 's are'} still open. The reviewer will see ${serious === 1 ? 'it' : 'them'}.`,
        confirmLabel: 'Submit anyway',
      });
      if (!ok) return;
    }
    setBusy('submit');
    try {
      hydrate(await api.submitForReview(item.id));
      toast('Sent to the approval queue.', 'success');
      onChanged();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(null);
    }
  };

  const decide = async (note: string, evidence = false) => {
    if (!item || !decision) return;
    setBusy('decide');
    try {
      const d = await api.recordDecision(item.id, { decision, comments: note || undefined, version_number: item.current_version_number, evidence_confirmed: evidence });
      hydrate(d);
      if (decision === 'approved' && d.status !== 'approved') {
        toast('Approval recorded. More approvals are required by policy; see the Approval tab.', 'info');
        setPanel('approval');
      } else {
        toast(decision === 'approved' ? `Approved v${d.current_version_number}.` : decision === 'rejected' ? 'Rejected.' : 'Sent back to the author.', 'success');
      }
      setDecision(null);
      onChanged();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(null);
    }
  };

  const restore = async (v: ContentVersion) => {
    if (!item) return;
    const ok = await confirm({
      title: `Restore version ${v.version_number}?`,
      body: 'This saves the earlier text as a new version. Nothing is deleted.',
      confirmLabel: 'Restore',
    });
    if (!ok) return;
    try {
      hydrate(
        await api.updateContentItem(item.id, { body: v.body, change_summary: `Restored text from v${v.version_number}` }),
      );
      toast(`Restored v${v.version_number} as a new version.`, 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const postComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item || !comment.trim()) return;
    setBusy('comment');
    try {
      await api.addComment(item.id, { text: comment.trim(), author_name: '', author_role: '' });
      hydrate(await api.getContentItem(item.id));
      setComment('');
    } catch (err: any) {
      toast(err.message, 'error');
    } finally {
      setBusy(null);
    }
  };

  const reviseCreative = async (file: File) => {
    if (!item) return;
    setBusy('save');
    try {
      const d = await api.uploadRevisedCreative(item.id, file);
      hydrate(d);
      toast(`Uploaded as v${d.current_version_number}. Run the analysis on the new creative.`, 'success');
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(null);
      if (reviseRef.current) reviseRef.current.value = '';
    }
  };

  const discard = () => {
    setBody(saved.body);
    setTitle(saved.title);
    setType(saved.type);
  };

  const selectFinding = (f: Finding) => {
    setSelected(f.id);
    if (effectiveMode === 'marked') {
      document.getElementById(`mark-${f.id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    } else if (!stale && f.end_offset > f.start_offset && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(f.start_offset, f.end_offset);
    }
  };

  // Keyboard: Ctrl/Cmd+S saves, Ctrl/Cmd+Enter runs the review.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      if (e.key === 's') {
        e.preventDefault();
        save();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        runReview();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (loading) {
    return <div className="flex flex-1 items-center justify-center text-[13px] text-ink-500">Loading…</div>;
  }

  /* ---------------- render ---------------- */
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-white px-4 py-2.5 sm:px-6">
        <button onClick={() => navigate('reviews')} className="flex items-center gap-1 text-[13px] text-ink-500 hover:text-ink-900">
          <ArrowLeft className="h-3.5 w-3.5" /> Reviews
        </button>
        <div className="flex min-w-0 flex-1 basis-[22rem] items-center gap-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Untitled piece"
            aria-label="Title"
            className="min-w-0 flex-1 rounded px-1.5 py-1 text-[15px] font-semibold text-ink-900 placeholder:font-normal placeholder:text-ink-400 hover:bg-ink-50 focus:bg-ink-50 focus:outline-none"
          />
          <div className="hidden shrink-0 items-center gap-3 text-[12.5px] text-ink-500 md:flex">
            <StatusPill status={status} />
            {item && <span className="tabular-nums">v{item.current_version_number}</span>}
            {dirty && <span className="text-amber-700">Unsaved</span>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {dirty && item && (
            <Button variant="ghost" size="sm" onClick={discard}>
              Discard
            </Button>
          )}
          {item && item.versions.length > 0 && (
            <Button size="sm" variant="ghost" onClick={() => navigate('replay', item.id)} title="Decision replay: compare versions, findings and history">
              <HistoryIcon className="h-3.5 w-3.5" /> Replay
            </Button>
          )}
          {isImage && canEdit && (
            <>
              <input ref={reviseRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={(e) => e.target.files?.[0] && reviseCreative(e.target.files[0])} />
              <Button size="sm" onClick={() => reviseRef.current?.click()} disabled={!!busy}>
                <ImageUp className="h-3.5 w-3.5" /> Upload revision
              </Button>
            </>
          )}
          {!isImage && canEdit && (
            <Button size="sm" onClick={save} disabled={!!busy || (!!item && !dirty)} title="Ctrl+S">
              {busy === 'save' ? 'Saving…' : 'Save'}
            </Button>
          )}
          <Button size="sm" variant={canSubmit || status === 'in_review' ? 'secondary' : 'primary'} onClick={runReview} disabled={!!busy || (!item && !canEdit)} title="Ctrl+Enter">
            {busy === 'review' ? (isImage ? 'Analysing creative…' : 'Checking…') : review ? 'Re-run analysis' : 'Run analysis'}
          </Button>
          {canSubmit && (
            <Button size="sm" variant="primary" onClick={submit} disabled={!!busy}>
              Submit for approval
            </Button>
          )}
          {status === 'in_review' && canDecide && (
            <>
              <Button size="sm" onClick={() => setDecision('changes_requested')}>
                Request changes
              </Button>
              <Button size="sm" variant="danger" onClick={() => setDecision('rejected')}>
                Reject
              </Button>
              <Button size="sm" variant="accent" onClick={() => setDecision('approved')}>
                Approve
              </Button>
            </>
          )}
          {status === 'in_review' && !canDecide && <span className="text-[12.5px] text-ink-500">Waiting for a reviewer</span>}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Document */}
        <div className="flex min-h-[40vh] min-w-0 flex-1 flex-col bg-paper lg:min-h-0">
          <div className={cx('flex flex-wrap items-center gap-3 border-b border-line px-4 py-2 text-[12.5px] text-ink-500 sm:px-6', isImage && 'hidden')}>
            <div className="inline-flex rounded-md border border-line bg-white p-0.5" role="group" aria-label="View">
              {(['edit', 'marked'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  disabled={m === 'marked' && (stale || !review)}
                  title={m === 'marked' && (stale || !review) ? 'Run a review on the current text to see marked findings' : undefined}
                  className={cx(
                    'rounded px-2.5 py-0.5 transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                    effectiveMode === m ? 'bg-pine-600 text-white' : 'text-ink-600 hover:text-ink-900',
                  )}
                >
                  {m === 'edit' ? 'Edit' : 'Marked up'}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1.5">
              <span>Channel</span>
              <select value={type} onChange={(e) => setType(e.target.value)} className="rounded border border-line bg-white px-1.5 py-0.5 text-[12.5px] text-ink-800 focus:outline-none">
                {Object.entries(CONTENT_TYPES).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <span className={cx('ml-auto tabular-nums', body.length > MAX_CHARS && 'font-medium text-red-700')}>
              {words} words · {body.length.toLocaleString()} chars
            </span>
          </div>

          {stale && !isImage && (
            <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-[12.5px] text-amber-900 sm:px-6">
              {bodyDirty
                ? 'You have unsaved edits. Findings below refer to the last reviewed text.'
                : `Findings are from v${reviewedVersion?.version_number ?? '?'}. The text has changed since then.`}{' '}
              <button onClick={runReview} disabled={!!busy} className="font-medium underline underline-offset-2">
                Re-run review
              </button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            <div className={cx('mx-auto px-6 py-10', isImage ? 'max-w-[760px] py-6' : 'max-w-[68ch]')}>
              {isImage && item?.image ? (
                <CreativeView image={item.image} findings={stale ? [] : findings} selected={selected} onSelect={(id) => {
                  setSelected(id);
                  setPanel('findings');
                  document.getElementById(`finding-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                }} />
              ) : effectiveMode === 'marked' && review ? (
                <MarkedText text={body} findings={findings} selected={selected} onSelect={(id) => {
                  setSelected(id);
                  setPanel('findings');
                  document.getElementById(`finding-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                }} />
              ) : (
                <>
                  {!item && !body && (
                    <div className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-dashed border-ink-300 bg-white px-4 py-3 text-[13px] text-ink-600">
                      <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-ink-500">Demo</span>
                      <span className="flex-1">Nothing to hand? Load fictional promo copy that breaks a few rules on purpose.</span>
                      <Button
                        size="sm"
                        onClick={() => {
                          setBody(SAMPLE_COPY);
                          if (!title) setTitle('Q4 cloud promotion — draft');
                        }}
                      >
                        Use sample copy
                      </Button>
                    </div>
                  )}
                  {!canEdit && <p className="mb-4 rounded-md bg-ink-100 px-3 py-2 text-[12.5px] text-ink-600">Reviewers can read and comment but not edit content. Ask the author for changes.</p>}
                  <textarea
                    ref={textareaRef}
                    readOnly={!canEdit}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder="Paste or write the copy you want checked…"
                    aria-label="Content"
                    className="min-h-[50vh] w-full resize-none bg-transparent text-[16px] leading-[1.8] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                    style={{ fieldSizing: 'content' } as React.CSSProperties}
                  />
                </>
              )}
            </div>
          </div>
        </div>

        {/* Side panel */}
        <aside className="flex min-h-0 w-full shrink-0 flex-col border-t border-line bg-white lg:w-[340px] xl:w-[400px] lg:border-l lg:border-t-0">
          <div className="px-4 pt-3">
            <Tabs
              value={panel}
              onChange={setPanel}
              items={[
                { id: 'findings', label: 'Findings', count: review ? openFindings.length : undefined },
                { id: 'claims', label: 'Claims', count: review ? (contradictedClaims || claimChecks.length) : undefined },
                { id: 'approval', label: 'Approval' },
                { id: 'history', label: 'History', count: item?.versions.length },
                { id: 'discussion', label: 'Discussion', count: item ? item.comments.length : undefined },
              ]}
            />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {panel === 'findings' && (
              <>
                {!review ? (
                  <div className="px-6 py-12 text-center text-[13px] text-ink-500">
                    <span className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-pine-50 text-pine-700">
                      <FileText className="h-5 w-5" />
                    </span>
                    <p className="mt-3 text-[14px] font-medium text-ink-900">No review yet</p>
                    <p className="mx-auto mt-1 max-w-[30ch] leading-relaxed">
                      Run a review to check this text against the {brand.name} rulebook. Nothing is published.
                    </p>
                    <ol className="mx-auto mt-5 max-w-[30ch] space-y-1.5 text-left text-[12.5px]">
                      <li>1. Write or paste your copy</li>
                      <li>2. Run review to see findings</li>
                      <li>3. Apply fixes, then submit for approval</li>
                    </ol>
                  </div>
                ) : (
                  <>
                    {/* Summary */}
                    <div className="border-b border-line px-4 py-3.5">
                      <div className="flex items-baseline justify-between gap-3">
                        <p className="text-[12.5px] text-ink-500">
                          Review of v{reviewedVersion?.version_number ?? '?'} · {timeAgo(review.created_at)}
                        </p>
                        <p className="text-[12.5px] font-medium text-ink-800">
                          {openFindings.length === 0 ? 'No open findings' : `${openFindings.length} open finding${openFindings.length === 1 ? '' : 's'}`}
                        </p>
                      </div>
                      <div className="mt-2.5 grid grid-cols-4 gap-px overflow-hidden rounded-md border border-line bg-line text-center">
                        {SEVERITIES.map((s) => (
                          <button
                            key={s}
                            onClick={() => setSevFilter(sevFilter === s ? 'all' : s)}
                            className={cx('bg-white px-1 py-1.5 hover:bg-ink-50', sevFilter === s && 'bg-ink-50 ring-1 ring-inset ring-pine-600')}
                            aria-pressed={sevFilter === s}
                          >
                            <span className={cx('block text-[16px] font-semibold tabular-nums', openSeverity(s) ? SEV_META[s].text : 'text-ink-300')}>{openSeverity(s)}</span>
                            <span className="block text-[11px] text-ink-500">{SEV_META[s].label}</span>
                          </button>
                        ))}
                      </div>
                      <div className="mt-2.5 flex items-center justify-between gap-2 text-[12px] text-ink-500">
                        <span>
                          {review.engine_type === 'hybrid_ai' ? 'Rules + AI' : 'Rule engine'}
                          {review.ai_status === 'fallback_rule_based' && ' · AI not configured'}
                          {review.ai_status === 'failed' && ' · AI step failed, rules only'}
                        </span>
                        <select
                          value={srcFilter}
                          onChange={(e) => setSrcFilter(e.target.value as SourceFilter)}
                          aria-label="Filter by source"
                          className="rounded border border-line bg-white px-1.5 py-0.5 text-[12px] text-ink-700 focus:outline-none"
                        >
                          <option value="all">All sources</option>
                          <option value="rule">Rulebook</option>
                          <option value="builtin">Built-in checks</option>
                          <option value="ai">AI suggestions</option>
                        </select>
                      </div>
                    </div>

                    {visible.length === 0 ? (
                      <p className="px-5 py-10 text-center text-[13px] text-ink-500">
                        {findings.length === 0 ? 'No issues found against the current rulebook.' : 'Nothing matches these filters.'}
                      </p>
                    ) : (
                      <ul>
                        {visible.map((f) => (
                          <FindingRow
                            key={f.id}
                            f={f}
                            selected={selected === f.id}
                            busy={!!busy}
                            editing={editing?.id === f.id ? editing.text : null}
                            onSelect={() => (selected === f.id ? setSelected(null) : selectFinding(f))}
                            onEdit={(text) => setEditing(text === null ? null : { id: f.id, text })}
                            onApply={(custom) => startApply(f, custom)}
                            onDismiss={() => dismiss(f)}
                            canApply={canEdit && !isImage}
                            canDismiss={canDecide}
                            imageItem={isImage}
                          />
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </>
            )}

            {panel === 'claims' && (
              review ? (
                <ClaimsPanel checks={claimChecks} stale={stale} onOpenSource={(docId) => navigate('sources', docId)}
                  onSelect={(c) => !isImage && textareaRef.current && effectiveMode === 'edit' && textareaRef.current.setSelectionRange(c.start_offset, c.end_offset)} />
              ) : (
                <p className="px-6 py-10 text-center text-[13px] text-ink-500">Run the analysis to check this content’s claims against approved sources.</p>
              )
            )}

            {panel === 'approval' && (
              item ? (
                <ApprovalPanel item={item} canPublish={canPublish} toast={toast} onPublished={reload} />
              ) : (
                <p className="px-6 py-10 text-center text-[13px] text-ink-500">Save the piece to see its approval requirements.</p>
              )
            )}

            {panel === 'history' && (
              <div className="px-4 py-3">
                {!item ? (
                  <p className="py-8 text-center text-[13px] text-ink-500">Save the piece to start a version history.</p>
                ) : (
                  <>
                    {item.decisions.length > 0 && (
                      <div className="mb-5">
                        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-ink-400">Decisions</p>
                        <ul className="space-y-2">
                          {item.decisions.map((d) => (
                            <li key={d.id} className="rounded-md border border-line px-3 py-2 text-[13px]">
                              <div className="flex items-center justify-between gap-2">
                                <StatusPill status={d.decision} />
                                <span className="text-[12px] text-ink-500">{formatDateTime(d.created_at)}</span>
                              </div>
                              <p className="mt-1 text-[12.5px] text-ink-600">
                                {d.reviewer_name}, {d.reviewer_role} · v{item.versions.find((v) => v.id === d.content_version_id)?.version_number ?? '?'}
                              </p>
                              {d.comments && <p className="mt-1.5 text-ink-800">{d.comments}</p>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-ink-400">Versions</p>
                    <ol className="relative space-y-4 border-l border-line pl-4">
                      {item.versions.map((v) => {
                        const current = v.version_number === item.current_version_number;
                        return (
                          <li key={v.id} className="relative">
                            <span className={cx('absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ring-2 ring-white', current ? 'bg-pine-600' : 'bg-ink-300')} />
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-[13px] font-medium text-ink-900">
                                v{v.version_number} {current && <span className="ml-1 font-normal text-ink-500">current</span>}
                              </p>
                              {!current && (
                                <button onClick={() => restore(v)} className="flex items-center gap-1 text-[12px] text-ink-500 hover:text-ink-900">
                                  <RotateCcw className="h-3 w-3" /> Restore
                                </button>
                              )}
                            </div>
                            <p className="text-[12px] text-ink-500">
                              {v.created_by} · {formatDateTime(v.created_at)}
                            </p>
                            {v.change_summary && <p className="mt-1 text-[12.5px] text-ink-700">{v.change_summary}</p>}
                            <p className="mt-1.5 line-clamp-2 rounded border border-line/70 bg-ink-50/70 p-2 font-mono text-[12px] text-ink-600">{v.body}</p>
                          </li>
                        );
                      })}
                    </ol>
                  </>
                )}
              </div>
            )}

            {panel === 'discussion' && (
              <div className="px-4 py-3">
                {!item ? (
                  <p className="py-8 text-center text-[13px] text-ink-500">Save the piece to start a discussion.</p>
                ) : (
                  <>
                    {item.comments.length === 0 ? (
                      <p className="py-6 text-center text-[13px] text-ink-500">No comments yet.</p>
                    ) : (
                      <ul className="space-y-4">
                        {item.comments.map((c) => (
                          <li key={c.id} className="text-[13px]">
                            <p>
                              <span className="font-medium text-ink-900">{c.author_name}</span>
                              <span className="text-ink-500"> · {c.author_role} · {timeAgo(c.created_at)}</span>
                            </p>
                            <p className="mt-1 whitespace-pre-wrap leading-relaxed text-ink-700">{c.text}</p>
                          </li>
                        ))}
                      </ul>
                    )}
                    <form onSubmit={postComment} className="mt-5">
                      <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        rows={3}
                        placeholder={`Comment as ${actor.name}…`}
                        className={inputCls}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) postComment(e as unknown as React.FormEvent);
                        }}
                      />
                      <div className="mt-2 flex justify-end">
                        <Button size="sm" variant="primary" type="submit" disabled={!comment.trim() || busy === 'comment'}>
                          Comment
                        </Button>
                      </div>
                    </form>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>

      <DecisionModal
        decision={decision}
        version={item?.current_version_number}
        evidencePrompt={claimChecks.some((c) => c.status !== 'supported')}
        busy={busy === 'decide'}
        onClose={() => setDecision(null)}
        onSubmit={decide}
        warning={
          decision === 'approved' && (stale || !review)
            ? 'The current version has not been reviewed against the rulebook.'
            : decision === 'approved' && openFindings.some((f) => f.severity === 'critical' || f.severity === 'high')
              ? 'There are open critical or high findings on this version. Approving records that you accepted them.'
              : undefined
        }
      />

      <Modal
        open={!!chooser}
        onClose={() => setChooser(null)}
        title="Which occurrence?"
        description={chooser ? `“${chooser.finding.matched_text}” appears ${chooser.positions.length} times. Pick the one to replace.` : undefined}
      >
        <ul className="space-y-2">
          {chooser?.positions.map((p) => {
            const len = chooser.finding.matched_text.length;
            return (
              <li key={p}>
                <button
                  onClick={() => apply(chooser.finding, chooser.custom, p)}
                  disabled={!!busy}
                  className="w-full rounded-md border border-line px-3 py-2 text-left font-mono text-[12.5px] text-ink-700 hover:border-ink-400 hover:bg-ink-50"
                >
                  …{body.slice(Math.max(0, p - 40), p)}
                  <mark className="rounded-sm bg-amber-100 px-0.5 text-ink-900">{body.slice(p, p + len)}</mark>
                  {body.slice(p + len, p + len + 40)}…
                </button>
              </li>
            );
          })}
        </ul>
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function MarkedText({ text, findings, selected, onSelect }: { text: string; findings: Finding[]; selected: string | null; onSelect: (id: string) => void }) {
  const spans = findings
    .filter((f) => !f.is_applied && f.end_offset > f.start_offset && f.end_offset <= text.length)
    .sort((a, b) => a.start_offset - b.start_offset);
  const missing = findings.filter((f) => !f.is_applied && f.start_offset === f.end_offset);

  const out: React.ReactNode[] = [];
  let pos = 0;
  for (const f of spans) {
    if (f.start_offset < pos) continue; // overlapping span already rendered
    if (f.start_offset > pos) out.push(text.slice(pos, f.start_offset));
    out.push(
      <mark
        key={f.id}
        id={`mark-${f.id}`}
        role="button"
        tabIndex={0}
        onClick={() => onSelect(f.id)}
        onKeyDown={(e) => e.key === 'Enter' && onSelect(f.id)}
        title={CATEGORY_LABEL[f.category] ?? f.category}
        className={cx(
          'cursor-pointer rounded-[2px] px-[1px] text-inherit underline decoration-2 underline-offset-[5px] outline-none',
          SEV_META[f.severity]?.mark,
          selected === f.id && 'ring-2 ring-pine-500',
        )}
      >
        {text.slice(f.start_offset, f.end_offset)}
      </mark>,
    );
    pos = f.end_offset;
  }
  out.push(text.slice(pos));

  return (
    <div>
      <div className="whitespace-pre-wrap text-[16px] leading-[1.8] text-ink-900">{out}</div>
      {missing.map((f) => (
        <button
          key={f.id}
          id={`mark-${f.id}`}
          onClick={() => onSelect(f.id)}
          className={cx(
            'mt-5 block w-full rounded-md border border-dashed border-amber-400 px-3 py-2 text-left text-[13px] text-amber-900 hover:bg-amber-50',
            selected === f.id && 'ring-2 ring-pine-500',
          )}
        >
          Missing: {CATEGORY_LABEL[f.category]?.toLowerCase() ?? 'required text'}
        </button>
      ))}
    </div>
  );
}

interface FindingRowProps {
  f: Finding;
  selected: boolean;
  busy: boolean;
  editing: string | null;
  onSelect: () => void;
  onEdit: (text: string | null) => void;
  onApply: (custom?: string) => void;
  onDismiss: () => void;
  canApply: boolean;
  canDismiss: boolean;
  imageItem: boolean;
}

function FindingRow({ f, selected, busy, editing, onSelect, onEdit, onApply, onDismiss, canApply, canDismiss, imageItem }: FindingRowProps) {
  const src = sourceOf(f);
  const zeroWidth = f.start_offset === f.end_offset && f.category === 'required_phrase';
  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation();
    fn();
  };

  return (
    <li id={`finding-${f.id}`} className={cx('border-b border-l-[3px] border-b-line', SEV_META[f.severity]?.edge, selected ? 'bg-ink-50' : 'bg-white', f.is_applied && 'opacity-60')}>
      <button
        onClick={onSelect}
        aria-expanded={selected}
        className="flex w-full items-start gap-2 px-4 py-3 text-left transition-colors hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-pine-500/60"
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2 text-[12.5px]">
            <SeverityTag severity={f.severity} />
            <span className="font-medium text-ink-900">{CATEGORY_LABEL[f.category] ?? f.category}</span>
            <span className="ml-auto shrink-0 text-[11.5px] text-ink-400">{SOURCE_LABEL[src]}</span>
          </span>
          <span className={cx('mt-1.5 block text-[13.5px] leading-snug', zeroWidth ? 'italic text-ink-500' : 'font-medium text-ink-900', !selected && 'truncate')}>
            {zeroWidth ? 'Missing from the text' : `“${f.matched_text}”`}
          </span>
          {f.is_applied && (
            <span className="mt-1 flex items-center gap-1 text-[12px] font-medium text-pine-700">
              <Check className="h-3.5 w-3.5" /> Suggestion applied
            </span>
          )}
        </span>
        <ChevronDown className={cx('mt-0.5 h-4 w-4 shrink-0 text-ink-400 transition-transform', selected && 'rotate-180')} aria-hidden />
      </button>

      {selected && (
        <div className="space-y-3 px-4 pb-4">
          <section>
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">Why it matters</h4>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-700">{f.explanation}</p>
          </section>

          {/* Evidence is kept visually separate from the explanation and the suggestion. */}
          <section className="flex gap-2.5 rounded-lg border border-line bg-white px-3 py-2.5">
            <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" aria-hidden />
            <div className="min-w-0 text-[12.5px]">
              <p className="font-medium text-ink-800">{src === 'ai' ? 'AI-assisted finding' : src === 'rule' ? 'Brand rule' : 'Built-in check'}</p>
              <p className={cx('mt-0.5 leading-snug', f.source_reference ? 'text-ink-600' : 'italic text-ink-400')}>
                {f.source_reference || 'No approved source is attached to this finding.'}
              </p>
              {(f.requires_human_review || src === 'ai') && (
                <p className="mt-1 flex flex-wrap gap-x-3 text-[12px]">
                  {f.requires_human_review && <span className="text-amber-800">Needs human verification</span>}
                  {src === 'ai' && <span className="text-ink-500">{Math.round(f.confidence * 100)}% model confidence</span>}
                </p>
              )}
            </div>
          </section>

          {f.confidence < 1 && src !== 'ai' && (
            <p className="text-[12px] text-ink-500">Confidence {Math.round(f.confidence * 100)}% · {f.finding_source === 'visual' ? 'measured from pixels' : f.finding_source === 'ocr' || f.finding_source === 'ocr_rule' ? 'rule applied to OCR text' : f.finding_source === 'evidence' ? 'evidence check' : 'deterministic rule'}</p>
          )}
          {!f.is_applied && imageItem && f.suggested_correction && (
            <section className="rounded-lg border border-pine-100 bg-pine-50 px-3 py-2.5">
              <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-pine-700">Suggested wording</h4>
              <p className="mt-1 whitespace-pre-wrap text-[13.5px] font-medium leading-snug text-ink-900">{f.suggested_correction.trim()}</p>
              <p className="mt-1 text-[12px] text-ink-500">Update the artwork and upload a revision; image text can’t be edited in place.</p>
            </section>
          )}
          {!f.is_applied && !canApply && canDismiss && (
            <div className="flex justify-end">
              <Button size="sm" variant="ghost" className="text-ink-500" onClick={stop(onDismiss)}>Dismiss</Button>
            </div>
          )}
          {!f.is_applied && canApply && (
            <div>
              {editing !== null ? (
                <div className="space-y-2">
                  <Field label="Replace with">
                    <input
                      className={inputCls}
                      value={editing}
                      onChange={(e) => onEdit(e.target.value)}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') onApply(editing);
                        if (e.key === 'Escape') onEdit(null);
                      }}
                    />
                  </Field>
                  <div className="flex gap-2">
                    <Button size="sm" variant="primary" disabled={busy} onClick={() => onApply(editing)}>
                      <CornerDownLeft className="h-3 w-3" /> Apply edit
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => onEdit(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  {f.suggested_correction && (
                    <section className="mb-2.5 rounded-lg border border-pine-100 bg-pine-50 px-3 py-2.5">
                      <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-pine-700">Suggested correction</h4>
                      <p className="mt-1 whitespace-pre-wrap text-[13.5px] font-medium leading-snug text-ink-900">{f.suggested_correction.trim()}</p>
                    </section>
                  )}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {f.suggested_correction && (
                      <>
                        <Button size="sm" variant="primary" disabled={busy} onClick={stop(() => onApply())}>
                          <Check className="h-3.5 w-3.5" /> Apply
                        </Button>
                        <Button size="sm" variant="ghost" onClick={stop(() => onEdit(f.suggested_correction ?? ''))}>
                          <Pencil className="h-3 w-3" /> Edit first
                        </Button>
                      </>
                    )}
                    {!f.suggested_correction && !zeroWidth && (
                      <Button size="sm" onClick={stop(() => onEdit(f.matched_text))}>
                        <Pencil className="h-3 w-3" /> Rewrite passage
                      </Button>
                    )}
                    {canDismiss && (
                      <Button size="sm" variant="ghost" className="ml-auto text-ink-500" onClick={stop(onDismiss)}>
                        Dismiss
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}
