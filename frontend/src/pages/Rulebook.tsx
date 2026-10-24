import React, { useCallback, useEffect, useState } from 'react';
import { Pencil, Plus, Search, Trash2, Upload } from 'lucide-react';
import {
  Button,
  CATEGORY_LABEL,
  EmptyState,
  Field,
  Modal,
  Page,
  PageHeader,
  SeverityTag,
  Skeleton,
  Switch,
  Tabs,
  cx,
  inputCls,
  useConfirm,
  useToast,
} from '../components/ui';
import type { ApprovedClaim, Brand, BrandRule } from '../types';
import { api } from '../api';

const RULE_CATEGORIES: BrandRule['category'][] = ['prohibited_term', 'preferred_term', 'required_phrase', 'restricted_claim', 'tone_voice', 'formatting_style'];

/** Field labels change with the category so the form explains itself. */
const PATTERN_COPY: Record<string, { pattern: string; replacement: string; patternHint: string; needsPattern: boolean }> = {
  prohibited_term: { pattern: 'Phrase to flag', replacement: 'Suggested replacement', patternHint: 'Matched as whole words, ignoring case.', needsPattern: true },
  preferred_term: { pattern: 'Term to avoid', replacement: 'Preferred term', patternHint: 'e.g. “users” — flagged wherever it appears.', needsPattern: true },
  required_phrase: { pattern: 'Phrase that must appear', replacement: 'Text to append when missing', patternHint: 'Flagged when the text does not contain this phrase.', needsPattern: true },
  restricted_claim: { pattern: 'Claim wording to flag', replacement: 'Approved alternative', patternHint: '“your” also matches “their” and “our”.', needsPattern: true },
  tone_voice: { pattern: 'Phrase to flag (optional)', replacement: 'Suggested wording', patternHint: 'Without a phrase the rule is only used as AI guidance.', needsPattern: false },
  formatting_style: { pattern: 'Pattern to flag (optional)', replacement: 'Suggested replacement', patternHint: 'Used as guidance when left empty.', needsPattern: false },
};

const EMPTY_RULE: Partial<BrandRule> = {
  name: '',
  category: 'prohibited_term',
  description: '',
  rule_text: '',
  match_pattern: '',
  suggested_replacement: '',
  severity: 'high',
  source_reference: '',
  is_active: true,
};

export function Rulebook({ brand }: { brand: Brand }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [tab, setTab] = useState<'rules' | 'claims'>('rules');
  const [rules, setRules] = useState<BrandRule[] | null>(null);
  const [claims, setClaims] = useState<ApprovedClaim[] | null>(null);
  const [category, setCategory] = useState<string>('all');
  const [query, setQuery] = useState('');
  const [ruleForm, setRuleForm] = useState<Partial<BrandRule> | null>(null);
  const [claimForm, setClaimForm] = useState<Partial<ApprovedClaim> | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.getRules(brand.id), api.getClaims(brand.id)])
      .then(([r, c]) => {
        setRules(r);
        setClaims(c);
      })
      .catch((e) => toast(e.message, 'error'));
  }, [brand.id, toast]);

  useEffect(() => {
    setRules(null);
    setClaims(null);
    load();
  }, [load]);

  const toggle = async (rule: BrandRule) => {
    try {
      const updated = await api.updateRule(brand.id, rule.id, { is_active: !rule.is_active });
      setRules((rs) => rs?.map((r) => (r.id === rule.id ? updated : r)) ?? null);
      toast(`${updated.is_active ? 'Enabled' : 'Disabled'} “${rule.name}”. Applies to the next review.`, 'info');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const removeRule = async (rule: BrandRule) => {
    const ok = await confirm({
      title: `Delete “${rule.name}”?`,
      body: 'Past findings keep their text but lose the link to this rule. Consider disabling it instead.',
      confirmLabel: 'Delete rule',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteRule(brand.id, rule.id);
      setRules((rs) => rs?.filter((r) => r.id !== rule.id) ?? null);
      toast('Rule deleted.', 'info');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const removeClaim = async (claim: ApprovedClaim) => {
    const ok = await confirm({ title: 'Remove this approved claim?', body: claim.claim_statement, confirmLabel: 'Remove', danger: true });
    if (!ok) return;
    try {
      await api.deleteClaim(brand.id, claim.id);
      setClaims((cs) => cs?.filter((c) => c.id !== claim.id) ?? null);
      toast('Claim removed.', 'info');
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  const q = query.trim().toLowerCase();
  const shownRules = (rules ?? []).filter(
    (r) =>
      (category === 'all' || r.category === category) &&
      (!q || [r.name, r.description, r.match_pattern, r.source_reference].some((v) => v?.toLowerCase().includes(q))),
  );
  const activeCount = (rules ?? []).filter((r) => r.is_active).length;

  return (
    <Page>
      <PageHeader
        title="Brand rulebook"
        description={`The rules and approved claims every ${brand.name} review is checked against. Changes apply to the next review you run.`}
        actions={
          <>
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="h-3.5 w-3.5" /> Import guideline
            </Button>
            {tab === 'rules' ? (
              <Button variant="primary" onClick={() => setRuleForm({ ...EMPTY_RULE })}>
                <Plus className="h-3.5 w-3.5" /> Add rule
              </Button>
            ) : (
              <Button variant="primary" onClick={() => setClaimForm({ claim_statement: '', topic: '', evidence_source: '', verification_date: new Date().toISOString().slice(0, 10), is_active: true })}>
                <Plus className="h-3.5 w-3.5" /> Add claim
              </Button>
            )}
          </>
        }
      />

      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { id: 'rules', label: `Rules · ${activeCount} active`, count: undefined },
          { id: 'claims', label: 'Approved claims', count: claims?.length },
        ]}
      />

      {tab === 'rules' && (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-1.5">
              {['all', ...RULE_CATEGORIES].map((c) => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  className={cx(
                    'rounded-full border px-2.5 py-0.5 text-[12.5px] transition-colors',
                    category === c ? 'border-pine-600 bg-pine-50 font-medium text-pine-700' : 'border-line bg-white text-ink-600 hover:border-ink-300',
                  )}
                >
                  {c === 'all' ? 'All' : CATEGORY_LABEL[c]}
                </button>
              ))}
            </div>
            <div className="relative sm:w-60">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-400" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search rules" aria-label="Search rules" className={`${inputCls} pl-8`} />
            </div>
          </div>

          {rules === null ? (
            <Skeleton className="h-72 w-full" />
          ) : shownRules.length === 0 ? (
            <EmptyState
              title={rules.length === 0 ? 'No rules yet' : 'No rules match'}
              body={rules.length === 0 ? 'Add the phrases, terms, and disclosures your brand cares about. Reviews only flag what is configured here plus a few built-in checks.' : 'Try a different category or search.'}
              action={rules.length === 0 && <Button variant="primary" onClick={() => setRuleForm({ ...EMPTY_RULE })}>Add the first rule</Button>}
            />
          ) : (
            <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-white">
              {shownRules.map((r) => (
                <li key={r.id} className={cx('flex gap-4 px-4 py-3.5', !r.is_active && 'bg-ink-50/60')}>
                  <div className="pt-0.5">
                    <Switch checked={r.is_active} onChange={() => toggle(r)} label={`${r.is_active ? 'Disable' : 'Enable'} ${r.name}`} />
                  </div>
                  <div className={cx('min-w-0 flex-1', !r.is_active && 'opacity-60')}>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <p className="text-[13.5px] font-medium text-ink-900">{r.name}</p>
                      <SeverityTag severity={r.severity} />
                      <span className="text-[12px] text-ink-500">{CATEGORY_LABEL[r.category]}</span>
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{r.description}</p>
                    {(r.match_pattern || r.suggested_replacement) && (
                      <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[12.5px]">
                        {r.match_pattern && <code className="rounded bg-red-50 px-1.5 py-px font-mono text-red-800">{r.match_pattern}</code>}
                        {r.match_pattern && r.suggested_replacement && <span className="text-ink-400">→</span>}
                        {r.suggested_replacement && <code className="rounded bg-pine-50 px-1.5 py-px font-mono text-pine-700">{r.suggested_replacement.trim()}</code>}
                      </p>
                    )}
                    {r.source_reference && <p className="mt-1.5 text-[12px] text-ink-400">{r.source_reference}</p>}
                  </div>
                  <div className="flex shrink-0 items-start gap-0.5">
                    <button onClick={() => setRuleForm({ ...r })} className="rounded p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-800" aria-label={`Edit ${r.name}`}>
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button onClick={() => removeRule(r)} className="rounded p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-700" aria-label={`Delete ${r.name}`}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === 'claims' && (
        <div className="space-y-3">
          <p className="max-w-2xl text-[13px] leading-relaxed text-ink-500">
            Performance and outcome claims in content are flagged as <em>unverified</em> unless they match a claim here. Absence from this list does not mean a claim is false,
            only that a person should check it.
          </p>
          {claims === null ? (
            <Skeleton className="h-48 w-full" />
          ) : claims.length === 0 ? (
            <EmptyState title="No approved claims" body="Add statements your legal or product team has signed off, with the evidence behind them." />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-line bg-white">
              <table className="w-full text-left text-[13.5px]">
                <thead>
                  <tr className="border-b border-line text-[12px] text-ink-500">
                    <th className="px-4 py-2 font-medium">Claim</th>
                    <th className="px-4 py-2 font-medium">Topic</th>
                    <th className="px-4 py-2 font-medium">Evidence</th>
                    <th className="px-4 py-2 font-medium">Verified</th>
                    <th className="w-10" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {claims.map((c) => (
                    <tr key={c.id}>
                      <td className="max-w-md px-4 py-3 font-medium text-[13.5px] text-ink-900">{c.claim_statement}</td>
                      <td className="px-4 py-3 text-ink-600">{c.topic}</td>
                      <td className="px-4 py-3 text-[12.5px] text-ink-500">{c.evidence_source}</td>
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums text-ink-500">{c.verification_date || '—'}</td>
                      <td className="pr-2 text-right">
                        <button onClick={() => removeClaim(c)} className="rounded p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-700" aria-label="Remove claim">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <RuleFormModal
        brand={brand}
        value={ruleForm}
        onChange={setRuleForm}
        onSaved={(rule, created) => {
          setRules((rs) => (created ? [rule, ...(rs ?? [])] : rs?.map((r) => (r.id === rule.id ? rule : r)) ?? null));
          setRuleForm(null);
          toast(created ? `Added “${rule.name}”.` : `Saved “${rule.name}”.`, 'success');
        }}
      />
      <ClaimFormModal
        brand={brand}
        value={claimForm}
        onChange={setClaimForm}
        onSaved={(claim) => {
          setClaims((cs) => [claim, ...(cs ?? [])]);
          setClaimForm(null);
          toast('Claim added.', 'success');
        }}
      />
      <UploadModal
        brand={brand}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onDone={() => {
          setUploadOpen(false);
          load();
        }}
      />
    </Page>
  );
}

/* ------------------------------------------------------------------ */

function RuleFormModal({
  brand,
  value,
  onChange,
  onSaved,
}: {
  brand: Brand;
  value: Partial<BrandRule> | null;
  onChange: (v: Partial<BrandRule> | null) => void;
  onSaved: (rule: BrandRule, created: boolean) => void;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  if (!value) return null;

  const isEdit = !!value.id;
  const copy = PATTERN_COPY[value.category ?? 'prohibited_term'];
  const set = (patch: Partial<BrandRule>) => onChange({ ...value, ...patch });
  const valid = (value.name?.trim().length ?? 0) >= 2 && !!value.description?.trim() && (!copy.needsPattern || !!value.match_pattern?.trim());

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    const payload: Partial<BrandRule> = {
      name: value.name!.trim(),
      category: value.category,
      severity: value.severity,
      description: value.description!.trim(),
      rule_text: value.rule_text?.trim() || value.description!.trim(),
      match_pattern: value.match_pattern?.trim() || undefined,
      suggested_replacement: value.suggested_replacement || undefined,
      source_reference: value.source_reference?.trim() || undefined,
      is_active: value.is_active ?? true,
    };
    try {
      const saved = isEdit ? await api.updateRule(brand.id, value.id!, payload) : await api.createRule(brand.id, payload);
      onSaved(saved, !isEdit);
    } catch (err: any) {
      toast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={() => onChange(null)}
      title={isEdit ? 'Edit rule' : 'Add rule'}
      width="max-w-xl"
      footer={
        <>
          <Button onClick={() => onChange(null)}>Cancel</Button>
          <Button variant="primary" type="submit" form="rule-form" disabled={!valid || saving}>
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Add rule'}
          </Button>
        </>
      }
    >
      <form id="rule-form" onSubmit={submit} className="space-y-3.5">
        <Field label="Name" required>
          <input className={inputCls} value={value.name ?? ''} onChange={(e) => set({ name: e.target.value })} placeholder="No outcome guarantees" autoFocus />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <select className={inputCls} value={value.category} onChange={(e) => set({ category: e.target.value as BrandRule['category'] })}>
              {RULE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Severity">
            <select className={inputCls} value={value.severity} onChange={(e) => set({ severity: e.target.value as BrandRule['severity'] })}>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={copy.pattern} required={copy.needsPattern} hint={copy.patternHint}>
            <input className={inputCls} value={value.match_pattern ?? ''} onChange={(e) => set({ match_pattern: e.target.value })} />
          </Field>
          <Field label={copy.replacement}>
            <input className={inputCls} value={value.suggested_replacement ?? ''} onChange={(e) => set({ suggested_replacement: e.target.value })} />
          </Field>
        </div>
        <Field label="Why this rule exists" required hint="Shown to writers next to every finding, so keep it plain.">
          <textarea className={inputCls} rows={2} value={value.description ?? ''} onChange={(e) => set({ description: e.target.value })} />
        </Field>
        <Field label="Source" hint="Where the rule comes from, e.g. “Legal policy §4.1”. Leave empty if there is none; nothing is invented.">
          <input className={inputCls} value={value.source_reference ?? ''} onChange={(e) => set({ source_reference: e.target.value })} />
        </Field>
      </form>
    </Modal>
  );
}

function ClaimFormModal({
  brand,
  value,
  onChange,
  onSaved,
}: {
  brand: Brand;
  value: Partial<ApprovedClaim> | null;
  onChange: (v: Partial<ApprovedClaim> | null) => void;
  onSaved: (c: ApprovedClaim) => void;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  if (!value) return null;
  const set = (patch: Partial<ApprovedClaim>) => onChange({ ...value, ...patch });
  const valid = !!value.claim_statement?.trim() && !!value.evidence_source?.trim();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    try {
      onSaved(
        await api.createClaim(brand.id, {
          claim_statement: value.claim_statement!.trim(),
          topic: value.topic?.trim() || 'General',
          evidence_source: value.evidence_source!.trim(),
          verification_date: value.verification_date || undefined,
          is_active: true,
        }),
      );
    } catch (err: any) {
      toast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={() => onChange(null)}
      title="Add approved claim"
      description="Only add claims that someone has actually verified."
      footer={
        <>
          <Button onClick={() => onChange(null)}>Cancel</Button>
          <Button variant="primary" type="submit" form="claim-form" disabled={!valid || saving}>
            {saving ? 'Saving…' : 'Add claim'}
          </Button>
        </>
      }
    >
      <form id="claim-form" onSubmit={submit} className="space-y-3.5">
        <Field label="Claim" required>
          <textarea className={inputCls} rows={2} value={value.claim_statement ?? ''} onChange={(e) => set({ claim_statement: e.target.value })} autoFocus />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Topic">
            <input className={inputCls} value={value.topic ?? ''} onChange={(e) => set({ topic: e.target.value })} placeholder="Performance" />
          </Field>
          <Field label="Verified on">
            <input type="date" className={inputCls} value={value.verification_date ?? ''} onChange={(e) => set({ verification_date: e.target.value })} />
          </Field>
        </div>
        <Field label="Evidence" required hint="The report, audit, or document that backs the claim.">
          <input className={inputCls} value={value.evidence_source ?? ''} onChange={(e) => set({ evidence_source: e.target.value })} />
        </Field>
      </form>
    </Modal>
  );
}

function UploadModal({ brand, open, onClose, onDone }: { brand: Brand; open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) setFile(null);
  }, [open]);

  const submit = async () => {
    if (!file) return;
    if (file.size > 1_000_000) {
      toast('That file is over 1 MB. Split it or paste the key rules manually.', 'error');
      return;
    }
    setBusy(true);
    try {
      const res = await api.uploadGuidelines(brand.id, file);
      toast(res.rules_extracted ? `Imported ${res.rules_extracted} rule${res.rules_extracted === 1 ? '' : 's'} from ${res.filename}. Review them before relying on them.` : `No rules could be extracted from ${res.filename}.`, res.rules_extracted ? 'success' : 'error');
      onDone();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Import a guideline"
      description="Plain text or Markdown only. Lines starting with “Prohibited:” or “Do not use:” become prohibited-wording rules, and lines like “use X instead of Y” become terminology rules. PDFs aren't supported yet."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!file || busy} onClick={submit}>
            {busy ? 'Importing…' : 'Import'}
          </Button>
        </>
      }
    >
      <label className="flex cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-ink-300 px-4 py-8 text-center hover:bg-ink-50">
        <Upload className="h-5 w-5 text-ink-400" />
        <span className="mt-2 text-[13px] text-ink-700">{file ? file.name : 'Choose a .txt or .md file'}</span>
        <span className="mt-0.5 text-[12px] text-ink-400">Up to 1 MB</span>
        <input type="file" accept=".txt,.md,text/plain,text/markdown" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
    </Modal>
  );
}
