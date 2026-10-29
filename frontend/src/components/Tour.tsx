import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Compass, Loader2, RotateCcw, X } from 'lucide-react';
import { Button, cx, useToast, type Role } from './ui';
import type { Brand, Me } from '../types';
import { api, type TourStatus } from '../api';

/**
 * Guided judge tour. It never performs governance actions itself: each step opens a real screen,
 * the person uses the normal controls, and the tour reads the stored records back from the API to
 * decide whether the step is done. Only the tour's own position lives in sessionStorage.
 */

const KEY = 'auditra.tour';
const START_EVENT = 'auditra:tour-start';

interface TourState {
  step: number;
  contentId: string | null;
  campaignId: string | null;
}

function load(): TourState | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as TourState) : null;
  } catch {
    return null;
  }
}

function save(s: TourState | null) {
  try {
    if (s) sessionStorage.setItem(KEY, JSON.stringify(s));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the tour still works until the page reloads */
  }
}

export function startTour() {
  save({ step: 0, contentId: null, campaignId: null });
  window.dispatchEvent(new Event(START_EVENT));
}

type Check = { done: boolean; lines: string[] };
type Persona = 'creator' | 'reviewer';

interface Step {
  title: string;
  screen: (s: TourState) => [string, string | null];
  persona?: Persona; // who should be signed in for this step
  instructions: string;
  check?: (s: TourState) => Promise<Check>;
}

const PERSONA_LABEL: Record<Persona, string> = { creator: 'Alex Rivers (content creator)', reviewer: 'Sarah Chen (compliance lead)' };

const STEPS: Step[] = [
  {
    title: 'Meet Northstar',
    screen: (s) => ['campaigns', s.campaignId],
    instructions:
      'Northstar Cloud is a fictional brand. Its “Atlas Pro launch” campaign has an approved brief and approved evidence sources. The tour follows one landing page from a real violation to an approved, replayable decision.',
  },
  {
    title: 'Analyse the landing page',
    screen: (s) => ['studio', `${s.contentId}?tab=claims`],
    persona: 'creator',
    instructions: 'Click “Run analysis” in the studio. Claims are checked against the stored source passages; the panel shows which ones the sources contradict.',
    check: async (s) => {
      const d = await api.getContentItem(s.contentId!);
      const current = d.latest_review && d.latest_review.content_version_id === d.current_version?.id;
      if (!current) return { done: false, lines: [`Version ${d.current_version_number} has not been analysed yet.`] };
      const bad = d.claim_checks.filter((c) => c.status === 'contradicted');
      return { done: true, lines: [`Analysed v${d.current_version_number}: ${d.claim_checks.length} claims checked, ${bad.length} contradicted by a source.`, ...bad.map((c) => `• “${c.claim_text}”`)] };
    },
  },
  {
    title: 'See it on the Risk Radar',
    screen: (s) => ['campaigns', s.campaignId],
    instructions: 'The campaign Risk Radar de-duplicates risks across assets. Open a risk to see the claim, the conflicting source passage and the source document.',
    check: async (s) => {
      const r = await api.getCampaignRisk(s.campaignId!);
      const mine = r.risks.filter((x) => x.asset_ids.includes(s.contentId!));
      if (!mine.length) return { done: false, lines: ['The radar has no stored risks for this asset yet. Go back and analyse it.'] };
      return { done: true, lines: [`Campaign level: ${r.level}. ${mine.length} risk(s) on this asset:`, ...mine.slice(0, 4).map((x) => `• ${x.severity}: ${x.evidence.text ?? x.title}`)] };
    },
  },
  {
    title: 'Fix it in the Fix tab',
    screen: (s) => ['studio', `${s.contentId}?tab=fix`],
    persona: 'creator',
    instructions:
      'Select the two factual fixes (date and price); each cites the fact-sheet passage. The security overview says Northstar is not HIPAA certified, so that claim can only be removed, not rewritten: select it too. Preview, then apply and confirm the factual change.',
    check: async (s) => {
      const d = await api.getContentItem(s.contentId!);
      const fix = d.versions.find((v) => v.version_number > 1 && (v.change_summary ?? '').startsWith('Remediation'));
      return fix
        ? { done: true, lines: [`Version ${fix.version_number} created by ${fix.created_by}: ${fix.change_summary}`] }
        : { done: false, lines: ['No remediation version yet. Apply the fixes to create one.'] };
    },
  },
  {
    title: 'Re-check and submit',
    screen: (s) => ['studio', `${s.contentId}?tab=claims`],
    persona: 'creator',
    instructions: 'Click “Re-run analysis” on the new version, read the updated claim results, then “Submit for approval”.',
    check: async (s) => {
      const d = await api.getContentItem(s.contentId!);
      const current = d.latest_review && d.latest_review.content_version_id === d.current_version?.id;
      const lines: string[] = [];
      if (!current) return { done: false, lines: [`Version ${d.current_version_number} has not been analysed yet.`] };
      const by = (st: string) => d.claim_checks.filter((c) => c.status === st).length;
      lines.push(`v${d.current_version_number}: ${by('supported')} supported, ${by('contradicted')} contradicted, ${by('needs_review') + by('unsupported') + by('stale')} still need a reviewer’s judgement.`);
      if (d.status !== 'in_review' && d.status !== 'approved') lines.push(`Status is “${d.status.replace('_', ' ')}”. Submit it for review.`);
      return { done: d.status === 'in_review' || d.status === 'approved', lines };
    },
  },
  {
    title: 'Approve as a different person',
    screen: (s) => ['studio', `${s.contentId}?tab=approval`],
    persona: 'reviewer',
    instructions:
      'Authors cannot approve their own work, so switch to the compliance lead. Read the approval requirements, then approve the version. The server checks the role, the author, the version number and every policy.',
    check: async (s) => {
      const d = await api.getContentItem(s.contentId!);
      const a = d.approval_status;
      if (d.status === 'approved' && d.approved_version_id === d.current_version?.id)
        return { done: true, lines: [`Approved v${d.current_version_number} by ${a?.approvals.map((x) => x.reviewer_name).join(', ') || 'a reviewer'}.`] };
      return { done: false, lines: [`Status: ${d.status.replace('_', ' ')}.`, ...(a?.blocking ?? []).map((b) => `• Waiting on: ${b}`)] };
    },
  },
  {
    title: 'Replay the decision',
    screen: (s) => ['replay', s.contentId],
    instructions: 'Decision Replay rebuilds the history from stored records: the text diff between versions, which findings were resolved, and every approval event.',
    check: async (s) => {
      const r = await api.getReplay(s.contentId!);
      return { done: true, lines: [`${r.versions.length} versions, ${r.decisions.length} decision(s), ${r.timeline.length} audit events for this asset.`] };
    },
  },
];

export function Tour({ brand, me, role, navigate }: { brand: Brand; me: Me; role: Role; navigate: (page: string, id?: string | null) => void }) {
  const toast = useToast();
  const [state, setState] = useState<TourState | null>(load);
  const [status, setStatus] = useState<TourStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [check, setCheck] = useState<Check | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [minimised, setMinimised] = useState(false);
  const lastNav = useRef<string>('');

  useEffect(() => {
    const on = () => {
      setState(load());
      setStatus(null);
      setCheck(null);
      setMinimised(false);
      lastNav.current = '';
    };
    window.addEventListener(START_EVENT, on);
    return () => window.removeEventListener(START_EVENT, on);
  }, []);

  useEffect(() => {
    api.authConfig().then((c) => setDemoEnabled(c.demo_login)).catch(() => setDemoEnabled(false));
  }, []);

  const update = useCallback((s: TourState | null) => {
    save(s);
    setState(s);
  }, []);

  // Step 0 resolves which stored asset the story uses.
  const loadStatus = useCallback(async () => {
    setStatusError(null);
    try {
      const st = await api.getTourStatus(brand.id);
      setStatus(st);
      return st;
    } catch (e: any) {
      setStatusError(e.message);
      return null;
    }
  }, [brand.id]);

  useEffect(() => {
    if (state && !state.contentId && brand.is_sample) {
      loadStatus().then((st) => {
        if (st?.ready && st.asset && st.campaign) update({ ...state, contentId: st.asset.id, campaignId: st.campaign.id });
        else if (st?.campaign && !state.campaignId) update({ ...state, campaignId: st.campaign.id });
      });
    }
  }, [state, brand.is_sample, loadStatus, update]);

  const step = state ? STEPS[Math.min(state.step, STEPS.length - 1)] : null;
  const ready = !!state?.contentId && !!state?.campaignId;

  // Open the step's screen once when the step (or its asset) changes.
  useEffect(() => {
    if (!state || !step || !state.campaignId) return;
    if (state.step > 0 && !state.contentId) return;
    const [page, id] = step.screen(state);
    const key = `${state.step}:${page}:${id}`;
    if (lastNav.current === key) return;
    lastNav.current = key;
    navigate(page, id);
  }, [state, step, navigate]);

  const runCheck = useCallback(async () => {
    if (!state || !step?.check || !ready) {
      setCheck(null);
      return;
    }
    setChecking(true);
    try {
      setCheck(await step.check(state));
    } catch (e: any) {
      setCheck({ done: false, lines: [`Could not read the stored records: ${e.message}`] });
    } finally {
      setChecking(false);
    }
  }, [state, step, ready]);

  // Re-read the stored records while the step is open, so progress shows after the person acts.
  useEffect(() => {
    setCheck(null);
    runCheck();
    if (!step?.check) return;
    const t = window.setInterval(runCheck, 4000);
    return () => window.clearInterval(t);
  }, [runCheck, step]);

  if (!state || !step) return null;

  const exit = () => update(null);
  const restart = () => {
    lastNav.current = '';
    setStatus(null);
    setCheck(null);
    update({ step: 0, contentId: null, campaignId: null }); // resets only the tour's own position
  };
  const go = (n: number) => {
    lastNav.current = '';
    update({ ...state, step: Math.max(0, Math.min(STEPS.length - 1, n)) });
  };

  const switchTo = async (p: Persona) => {
    setBusy(true);
    try {
      await api.demoLogin(p);
      window.location.reload(); // the tour resumes from sessionStorage as the new persona
    } catch (e: any) {
      toast(e.message, 'error');
      setBusy(false);
    }
  };

  const createCopy = async () => {
    setBusy(true);
    try {
      const st = await api.createTourCopy(brand.id);
      setStatus(st);
      if (st.ready && st.asset && st.campaign) {
        update({ ...state, contentId: st.asset.id, campaignId: st.campaign.id });
        toast(`Using “${st.asset.title}”.`, 'success');
      }
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const wrongPersona = step.persona && (step.persona === 'reviewer' ? role === 'creator' : role === 'reviewer');
  const isLast = state.step === STEPS.length - 1;
  const gated = !!step.check && !check?.done;

  if (minimised) {
    return (
      <button onClick={() => setMinimised(false)} className="fixed bottom-5 left-5 z-40 flex items-center gap-2 rounded-full lg:left-[268px] bg-ink-900 px-4 py-2 text-[13px] font-medium text-white shadow-lg">
        <Compass className="h-4 w-4" /> Tour · step {state.step + 1} of {STEPS.length}
      </button>
    );
  }

  return (
    <aside role="dialog" aria-label="Guided tour" className="fixed bottom-5 left-5 z-40 w-[min(380px,calc(100vw-2.5rem))] lg:left-[268px] rounded-xl border border-line bg-white shadow-xl">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <Compass className="h-4 w-4 text-pine-600" />
        <span className="text-[12px] font-medium uppercase tracking-wide text-ink-500">Guided tour · step {state.step + 1} of {STEPS.length}</span>
        <button onClick={() => setMinimised(true)} className="ml-auto rounded px-1.5 text-[12px] text-ink-500 hover:bg-ink-100" aria-label="Minimise tour">–</button>
        <button onClick={exit} className="rounded p-0.5 text-ink-500 hover:bg-ink-100" aria-label="Exit tour"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex gap-1 px-4 pt-3" aria-hidden>
        {STEPS.map((_, i) => (
          <span key={i} className={cx('h-1 flex-1 rounded-full', i < state.step ? 'bg-pine-500' : i === state.step ? 'bg-pine-300' : 'bg-ink-100')} />
        ))}
      </div>

      <div className="max-h-[55vh] space-y-3 overflow-y-auto px-4 py-3 text-[13px] leading-relaxed text-ink-700">
        <h2 className="text-[15px] font-semibold text-ink-900">{step.title}</h2>

        {!brand.is_sample ? (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">The tour uses the fictional Northstar demo workspace. Switch to it from the workspace menu to continue.</p>
        ) : (
          <>
            <p>{step.instructions}</p>

            {state.step === 0 && status?.campaign?.brief && (
              <p className="rounded-lg bg-ink-50 px-3 py-2 text-[12.5px] text-ink-600"><span className="font-medium text-ink-800">Campaign brief: </span>{status.campaign.brief}</p>
            )}
            {state.step === 0 && ready && status?.asset && (
              <p className="text-[12.5px] text-ink-600">Asset for this run: <span className="font-medium text-ink-800">{status.asset.title}</span> (v{status.asset.version}, {status.asset.kind === 'seeded' ? 'seeded fixture' : 'labelled tour copy'}).</p>
            )}

            {!ready && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">
                {statusError ? `Could not load the tour fixture: ${statusError}` : status?.message ?? 'Looking for the tour fixture…'}
                {status && !status.ready && status.problem !== 'missing_campaign' && (
                  <div className="mt-2">
                    {role === 'reviewer' ? (
                      demoEnabled && <Button size="sm" disabled={busy} onClick={() => switchTo('creator')}>Switch to Alex Rivers to create it</Button>
                    ) : (
                      <Button size="sm" variant="primary" disabled={busy} onClick={createCopy}>Create a labelled tour copy</Button>
                    )}
                  </div>
                )}
                {statusError && <div className="mt-2"><Button size="sm" onClick={loadStatus}>Try again</Button></div>}
              </div>
            )}

            {ready && wrongPersona && step.persona && (
              <div className="rounded-lg border border-line bg-ink-50 px-3 py-2 text-[12.5px]">
                You are signed in as {me.display_name} ({role}). This step is done by {PERSONA_LABEL[step.persona]}.
                {demoEnabled ? (
                  <div className="mt-2"><Button size="sm" variant="primary" disabled={busy} onClick={() => switchTo(step.persona!)}>Sign in as {PERSONA_LABEL[step.persona].split(' (')[0]}</Button></div>
                ) : (
                  <p className="mt-1 text-ink-500">Demo sign-in is disabled on this server; sign in as a member with that role.</p>
                )}
              </div>
            )}

            {ready && step.check && (
              <div className={cx('rounded-lg border px-3 py-2 text-[12.5px]', check?.done ? 'border-pine-200 bg-pine-50 text-pine-900' : 'border-line bg-white text-ink-600')}>
                <div className="mb-1 flex items-center gap-1.5 font-medium">
                  {checking && !check ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : check?.done ? <Check className="h-3.5 w-3.5" /> : <span className="h-2 w-2 rounded-full bg-amber-400" />}
                  {check?.done ? 'Done — read back from the stored records' : 'Waiting for this step'}
                </div>
                {check?.lines.map((l, i) => <p key={i} className="break-words">{l}</p>)}
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-line px-4 py-2.5">
        <Button size="sm" variant="ghost" onClick={restart} title="Start over. Records you created stay as they are."><RotateCcw className="h-3.5 w-3.5" /> Restart</Button>
        <div className="ml-auto flex gap-2">
          <Button size="sm" disabled={state.step === 0} onClick={() => go(state.step - 1)}><ArrowLeft className="h-3.5 w-3.5" /> Back</Button>
          {isLast ? (
            <Button size="sm" variant="primary" onClick={exit}>Finish</Button>
          ) : (
            <Button size="sm" variant="primary" disabled={!ready || gated} title={gated ? 'Complete this step first' : undefined} onClick={() => go(state.step + 1)}>
              Next <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
    </aside>
  );
}
