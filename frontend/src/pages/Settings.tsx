import { useEffect, useState } from 'react';
import { Button, Field, Page, PageHeader, Section, inputCls, useToast } from '../components/ui';
import type { Brand } from '../types';
import { api, type HealthStatus } from '../api';

interface SettingsProps {
  brand: Brand;
  health: HealthStatus | null;
  onBrandUpdated: (b: Brand) => void;
  onResetDemo: () => void;
}

export function Settings({ brand, health, onBrandUpdated, onResetDemo }: SettingsProps) {
  const toast = useToast();
  const [form, setForm] = useState({ name: brand.name, industry: brand.industry, description: brand.description ?? '', secondary_color: brand.secondary_color });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm({ name: brand.name, industry: brand.industry, description: brand.description ?? '', secondary_color: brand.secondary_color });
  }, [brand]);

  const dirty = form.name !== brand.name || form.industry !== brand.industry || form.description !== (brand.description ?? '') || form.secondary_color !== brand.secondary_color;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.name.trim().length < 2) {
      toast('The name needs at least two characters.', 'error');
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateBrand(brand.id, { ...form, name: form.name.trim() });
      onBrandUpdated(updated);
      toast('Workspace saved.', 'success');
    } catch (err: any) {
      toast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const aiOn = health?.ai_engine === 'configured';

  return (
    <Page width="max-w-3xl">
      <PageHeader title="Settings" />

      <Section title="Workspace">
        <form onSubmit={save} className="space-y-4 rounded-lg border border-line bg-white p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Brand name" required>
              <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Industry">
              <input className={inputCls} value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
            </Field>
          </div>
          <Field label="Description">
            <textarea className={inputCls} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="Workspace colour" hint="Used for the workspace badge in the sidebar.">
            <div className="flex items-center gap-2">
              <input type="color" value={form.secondary_color} onChange={(e) => setForm({ ...form, secondary_color: e.target.value })} className="h-8 w-10 cursor-pointer rounded border border-line bg-white p-0.5" />
              <span className="font-mono text-[12.5px] text-ink-500">{form.secondary_color}</span>
            </div>
          </Field>
          <div className="flex justify-end">
            <Button variant="primary" type="submit" disabled={!dirty || saving}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </form>
      </Section>

      <Section title="How reviews are checked">
        <div className="divide-y divide-line rounded-lg border border-line bg-white text-[13px]">
          <div className="flex gap-4 p-5">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-pine-500" />
            <div>
              <p className="font-medium text-ink-900">Rule engine · always on</p>
              <p className="mt-1 leading-relaxed text-ink-600">
                Matches the rulebook's phrases, terms, and required disclosures, plus a few built-in checks for unverified performance claims and shouty formatting. Same text and
                same rules always give the same findings. Runs on the server; nothing leaves it.
              </p>
            </div>
          </div>
          <div className="flex gap-4 p-5">
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${aiOn ? 'bg-pine-500' : 'bg-ink-300'}`} />
            <div>
              <p className="font-medium text-ink-900">AI review step · {health ? (aiOn ? 'configured' : 'not configured') : 'status unknown'}</p>
              <p className="mt-1 leading-relaxed text-ink-600">
                {aiOn
                  ? 'Content and the active rules are sent to the configured provider for tone and messaging checks. Rule references it returns are checked against the rulebook; unknown ones are dropped.'
                  : 'Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY on the server to enable it. Until then reviews are labelled “Rule engine” and no content is sent to a third party.'}
              </p>
            </div>
          </div>
        </div>
      </Section>

      {brand.is_sample && (
        <Section title="Demo data">
          <div className="flex flex-col gap-3 rounded-lg border border-line bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] leading-relaxed text-ink-600">Put the Northstar workspace back to its starting state: 7 rules, 3 approved claims, and three sample pieces. Anything you added here is removed.</p>
            <Button variant="danger" onClick={onResetDemo}>
              Reset demo workspace
            </Button>
          </div>
        </Section>
      )}
    </Page>
  );
}
