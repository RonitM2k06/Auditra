import React, { useEffect, useState } from 'react';
import { FileSearch, Image as ImageIcon, Network, ShieldCheck } from 'lucide-react';
import { Button, Field, inputCls, Logo } from '../components/ui';
import { api } from '../api';
import type { Me } from '../types';

const PERSONAS = [
  { id: 'creator', name: 'Alex Rivers', role: 'Content Creator', can: 'Writes copy, uploads creatives, applies fixes, submits for approval.' },
  { id: 'reviewer', name: 'Sarah Chen', role: 'Brand Compliance Lead', can: 'Reviews evidence, approves or rejects, publishes to the sandbox.' },
  { id: 'admin', name: 'Morgan Lee', role: 'Workspace Admin', can: 'Manages rules, sources, policies, members and visual identity.' },
];

export function Login({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [demo, setDemo] = useState(true);

  useEffect(() => {
    api.authConfig().then((c) => setDemo(c.demo_login)).catch(() => undefined);
  }, []);

  const run = async (key: string, fn: () => Promise<Me>) => {
    setBusy(key);
    setError(null);
    try {
      onSignedIn(await fn());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run('form', () => (mode === 'signin' ? api.login(email, password) : api.register(email, password, name)));
  };

  return (
    <div className="min-h-full overflow-y-auto bg-paper">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-10 sm:px-8 lg:grid-cols-[1.1fr_1fr] lg:py-16">
        <section>
          <Logo />
          <h1 className="mt-10 text-[30px] font-semibold leading-tight tracking-tight text-ink-900 sm:text-[36px]">
            Every claim traced to evidence. Every approval bound to a version.
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-600">
            AUDITRA checks marketing copy and image creatives against a brand’s rules and approved sources before anything ships,
            then enforces the approval policy on the server and only publishes the exact version that was approved.
          </p>
          <ul className="mt-8 grid gap-3 sm:grid-cols-2">
            {[
              { icon: ImageIcon, t: 'Creatives, not just copy', d: 'OCR, WCAG contrast, palette ΔE and logo similarity on real uploads.' },
              { icon: FileSearch, t: 'Evidence-grounded claims', d: 'Each claim is matched to a stored passage and classified conservatively.' },
              { icon: ShieldCheck, t: 'Server-enforced governance', d: 'Roles, approval policies, self-approval blocks and a guarded publish step.' },
              { icon: Network, t: 'Campaign consistency', d: 'Prices, dates and disclosures compared across every asset in a campaign.' },
            ].map(({ icon: Icon, t, d }) => (
              <li key={t} className="rounded-xl border border-line bg-white p-4">
                <Icon className="h-5 w-5 text-pine-600" strokeWidth={1.75} />
                <p className="mt-2 text-[14px] font-medium text-ink-900">{t}</p>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-600">{d}</p>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-5">
          {demo && (
            <div className="rounded-2xl border border-line bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-pine-700">Judge demo · no setup</p>
              <h2 className="mt-1 text-[17px] font-semibold text-ink-900">Explore the fictional Northstar workspace</h2>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-600">
                Pick a persona. Each is a real account with server-enforced permissions, limited to the shared demo workspace.
                Try the same action as different people to see what each role may do.
              </p>
              <div className="mt-4 space-y-2">
                {PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => run(p.id, () => api.demoLogin(p.id))}
                    disabled={!!busy}
                    className="flex w-full items-start gap-3 rounded-xl border border-line px-3.5 py-3 text-left transition-colors hover:border-pine-500 hover:bg-pine-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine-500/50 disabled:opacity-60"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-navy-900 text-[13px] font-semibold text-white">
                      {p.name.split(' ').map((w) => w[0]).join('')}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium text-ink-900">
                        {busy === p.id ? 'Signing in…' : p.name} <span className="font-normal text-ink-500">· {p.role}</span>
                      </span>
                      <span className="mt-0.5 block text-[12.5px] leading-snug text-ink-600">{p.can}</span>
                    </span>
                  </button>
                ))}
              </div>
              <p className="mt-3 text-[12px] leading-snug text-ink-500">The demo workspace is shared by everyone testing it and contains fictional data only.</p>
            </div>
          )}

          <form onSubmit={submit} className="rounded-2xl border border-line bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-ink-900">{mode === 'signin' ? 'Sign in' : 'Create an account'}</h2>
              <button type="button" onClick={() => { setMode(mode === 'signin' ? 'register' : 'signin'); setError(null); }} className="text-[13px] font-medium text-pine-700 hover:underline">
                {mode === 'signin' ? 'Create an account' : 'I have an account'}
              </button>
            </div>
            <p className="mt-1 text-[12.5px] text-ink-500">
              {mode === 'register' ? 'You become the admin of any workspace you create. Your workspaces are private to their members.' : 'Use the email and password you registered with.'}
            </p>
            <div className="mt-4 space-y-3">
              {mode === 'register' && (
                <Field label="Your name" required>
                  <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required minLength={2} />
                </Field>
              )}
              <Field label="Email" required>
                <input className={inputCls} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
              </Field>
              <Field label="Password" required hint={mode === 'register' ? 'At least 10 characters.' : undefined}>
                <input className={inputCls} type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 10 : 1} />
              </Field>
            </div>
            {error && <p role="alert" className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-800">{error}</p>}
            <Button type="submit" variant="primary" className="mt-4 w-full" disabled={!!busy}>
              {busy === 'form' ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}
