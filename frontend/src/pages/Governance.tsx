import { useCallback, useEffect, useRef, useState } from 'react';
import { Plus, Trash2, Upload } from 'lucide-react';
import { Button, EmptyState, Field, inputCls, Page, PageHeader, PageSkeleton, ROLE_LABEL, Section, Switch, useConfirm, useToast } from '../components/ui';
import type { Brand, Member, Policy, VisualIdentity, WorkspaceRole } from '../types';
import { api } from '../api';

const CONDITION_VALUES: Record<string, string[]> = {
  severity_at_least: ['critical', 'high', 'medium', 'low'],
  claim_status: ['contradicted', 'stale', 'needs_review', 'unsupported'],
  finding_category: ['restricted_claim', 'prohibited_term', 'unverified_claim', 'claim_contradicted', 'visual_contrast', 'visual_logo', 'required_phrase'],
};
const CONDITION_LABEL: Record<string, string> = {
  severity_at_least: 'An open finding at or above severity',
  claim_status: 'A claim is classified as',
  finding_category: 'An open finding in category',
};

export function Governance({ brand, role, me }: { brand: Brand; role: WorkspaceRole; me: string }) {
  const toast = useToast();
  const confirm = useConfirm();
  const isAdmin = role === 'admin';
  const [policies, setPolicies] = useState<Policy[] | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [visual, setVisual] = useState<VisualIdentity | null>(null);
  const [draft, setDraft] = useState({ name: '', condition_type: 'severity_at_least', condition_value: 'high', required_role: '', min_approvals: 1, require_evidence_confirmation: false });
  const [invite, setInvite] = useState({ email: '', role: 'creator' });
  const [colors, setColors] = useState('');
  const logoRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [p, m, v] = await Promise.all([api.getPolicies(brand.id), api.getMembers(brand.id), api.getVisualIdentity(brand.id)]);
      setPolicies(p);
      setMembers(m);
      setVisual(v);
      setColors(v.extra_colors.join(', '));
    } catch (e: any) {
      toast(e.message, 'error');
    }
  }, [brand.id, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      toast(ok, 'success');
      await load();
    } catch (e: any) {
      toast(e.message, 'error');
    }
  };

  if (!policies) return <PageSkeleton />;

  return (
    <Page width="max-w-4xl">
      <PageHeader
        title="Governance"
        description="Approval policies, workspace members and the visual identity used for creative checks. Every rule here is enforced by the server, and every change is recorded in the audit trail."
      />
      {!isAdmin && <p className="mb-6 rounded-md border border-line bg-white px-4 py-2.5 text-[13px] text-ink-600">You can view these settings. Only workspace admins can change them.</p>}

      <Section title="Approval policies" description="When content matches a condition, approving it needs the extra approvals listed. Every version always needs at least one reviewer or admin approval, and authors cannot approve their own content.">
        {policies.length === 0 ? (
          <EmptyState title="No policies yet" body="Without policies, one reviewer approval on an analysed version is enough." />
        ) : (
          <ul className="divide-y divide-line rounded-lg border border-line bg-white">
            {policies.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium text-ink-900">{p.name}</p>
                  <p className="text-[12.5px] text-ink-500">
                    {p.description} → {p.min_approvals} distinct approver{p.min_approvals > 1 ? 's' : ''}
                    {p.required_role ? `, including a ${ROLE_LABEL[p.required_role].toLowerCase()}` : ''}
                    {p.require_evidence_confirmation ? ', with evidence confirmed' : ''}
                  </p>
                </div>
                <Switch checked={p.is_active} label={`${p.name} active`} onChange={(v) => isAdmin && act(() => api.updatePolicy(brand.id, p.id, { ...p, is_active: v }), v ? 'Policy enabled.' : 'Policy disabled.')} />
                {isAdmin && (
                  <Button size="sm" variant="ghost" aria-label={`Delete ${p.name}`} onClick={async () => {
                    if (await confirm({ title: `Delete “${p.name}”?`, body: 'Content will no longer need the approvals this policy requires.', confirmLabel: 'Delete', danger: true })) {
                      act(() => api.deletePolicy(brand.id, p.id), 'Policy deleted.');
                    }
                  }}><Trash2 className="h-3.5 w-3.5" /></Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {isAdmin && (
          <form
            className="mt-3 grid gap-3 rounded-lg border border-dashed border-ink-300 bg-white p-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              act(() => api.createPolicy(brand.id, { ...draft, required_role: (draft.required_role || null) as Policy['required_role'] } as Partial<Policy>), 'Policy added.').then(() =>
                setDraft({ ...draft, name: '' }),
              );
            }}
          >
            <Field label="Policy name" required><input className={inputCls} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required minLength={3} /></Field>
            <Field label="When">
              <div className="flex gap-2">
                <select className={inputCls} value={draft.condition_type} onChange={(e) => setDraft({ ...draft, condition_type: e.target.value, condition_value: CONDITION_VALUES[e.target.value][0] })}>
                  {Object.entries(CONDITION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <select className={inputCls} value={draft.condition_value} onChange={(e) => setDraft({ ...draft, condition_value: e.target.value })}>
                  {CONDITION_VALUES[draft.condition_type].map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
            </Field>
            <Field label="Requires a">
              <select className={inputCls} value={draft.required_role} onChange={(e) => setDraft({ ...draft, required_role: e.target.value })}>
                <option value="">Any reviewer or admin</option>
                <option value="reviewer">Brand compliance lead</option>
                <option value="admin">Workspace admin</option>
              </select>
            </Field>
            <Field label="Distinct approvers">
              <input type="number" min={1} max={5} className={inputCls} value={draft.min_approvals} onChange={(e) => setDraft({ ...draft, min_approvals: Number(e.target.value) })} />
            </Field>
            <label className="flex items-center gap-2 text-[13px] text-ink-700 sm:col-span-2">
              <input type="checkbox" className="accent-pine-600" checked={draft.require_evidence_confirmation} onChange={(e) => setDraft({ ...draft, require_evidence_confirmation: e.target.checked })} />
              An approver must confirm they reviewed the claim evidence
            </label>
            <div className="sm:col-span-2"><Button type="submit" variant="primary" size="sm"><Plus className="h-3.5 w-3.5" /> Add policy</Button></div>
          </form>
        )}
      </Section>

      <Section title="Members" description="Roles are per workspace. Permissions are checked on every API call, so hiding a button is never the only protection.">
        <ul className="divide-y divide-line rounded-lg border border-line bg-white">
          {members.map((m) => (
            <li key={m.user_id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-[14px] text-ink-900">{m.display_name}{m.display_name === me && <span className="text-ink-500"> (you)</span>}{m.is_demo && <span className="ml-2 rounded bg-ink-100 px-1.5 text-[11px] text-ink-500">demo persona</span>}</p>
                <p className="text-[12.5px] text-ink-500">{m.email}</p>
              </div>
              {isAdmin ? (
                <select className="rounded border border-line bg-white px-2 py-1 text-[13px]" value={m.role} onChange={(e) => act(() => api.updateMember(brand.id, m.user_id, e.target.value), 'Role updated.')} aria-label={`Role for ${m.display_name}`}>
                  {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              ) : (
                <span className="text-[13px] text-ink-600">{m.role_label}</span>
              )}
              {isAdmin && (
                <Button size="sm" variant="ghost" aria-label={`Remove ${m.display_name}`} onClick={async () => {
                  if (await confirm({ title: `Remove ${m.display_name}?`, body: 'They lose access to this workspace immediately.', confirmLabel: 'Remove', danger: true })) {
                    act(() => api.removeMember(brand.id, m.user_id), 'Member removed.');
                  }
                }}><Trash2 className="h-3.5 w-3.5" /></Button>
              )}
            </li>
          ))}
        </ul>
        {isAdmin && (
          <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); act(() => api.addMember(brand.id, invite.email, invite.role), 'Member added.').then(() => setInvite({ ...invite, email: '' })); }}>
            <Field label="Add an existing account by email"><input type="email" className={inputCls} value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} required /></Field>
            <select className="h-9 rounded-md border border-line bg-white px-2 text-[13px]" value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })} aria-label="Role">
              {Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <Button type="submit" size="sm" variant="primary">Add</Button>
          </form>
        )}
      </Section>

      <Section title="Visual identity" description="Used by creative analysis: palette distance (CIE ΔE) and reference-logo similarity.">
        <div className="grid gap-4 rounded-lg border border-line bg-white p-5 sm:grid-cols-2">
          <div>
            <p className="text-[13px] font-medium text-ink-800">Approved palette</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {visual?.palette.map((c) => (
                <span key={c} className="flex items-center gap-1.5 rounded border border-line px-1.5 py-1 font-mono text-[11.5px] text-ink-700"><span className="h-4 w-4 rounded-sm border border-line" style={{ background: c }} />{c}</span>
              ))}
            </div>
            <p className="mt-2 text-[12px] text-ink-500">Primary and secondary colours come from Settings. Near-white and near-black are always treated as neutral.</p>
            {isAdmin && (
              <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); act(() => api.setPalette(brand.id, colors.split(/[\s,]+/).filter(Boolean)), 'Palette saved.'); }}>
                <input className={inputCls} value={colors} onChange={(e) => setColors(e.target.value)} placeholder="#FFFFFF, #E9EEF2" aria-label="Extra palette colours" />
                <Button type="submit" size="sm">Save</Button>
              </form>
            )}
          </div>
          <div>
            <p className="text-[13px] font-medium text-ink-800">Reference logo</p>
            {visual?.logo ? (
              <img src={`${visual.logo.url}?v=${Date.now() % 100000}`} alt="Reference logo" className="mt-2 max-h-20 rounded border border-line bg-white p-2" />
            ) : (
              <p className="mt-2 text-[12.5px] italic text-ink-500">None configured. Logo similarity is skipped until one is added.</p>
            )}
            {isAdmin && (
              <>
                <input ref={logoRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={(e) => e.target.files?.[0] && act(() => api.uploadLogo(brand.id, e.target.files![0]), 'Logo updated.')} />
                <Button size="sm" className="mt-3" onClick={() => logoRef.current?.click()}><Upload className="h-3.5 w-3.5" /> Upload logo (PNG/JPEG, ≤1 MB)</Button>
              </>
            )}
            <p className="mt-2 text-[12px] text-ink-500">Similarity uses normalised cross-correlation. It shows whether the logo looks present, not whether it is authentic or correctly placed.</p>
          </div>
        </div>
      </Section>
    </Page>
  );
}
