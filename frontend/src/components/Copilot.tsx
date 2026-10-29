import React, { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Send, X } from 'lucide-react';
import { cx } from './ui';
import { api } from '../api';

export interface CopilotAnswer {
  answer: string;
  mode: 'claude' | 'deterministic';
  notice?: string;
  model?: string;
  trace: Array<{ tool: string; input: Record<string, unknown>; output: unknown }>;
}

type Turn = { role: 'user'; content: string } | { role: 'assistant'; content: string; result: CopilotAnswer };

const SUGGESTIONS = [
  'What could go wrong in the Atlas Pro launch?',
  'Which content has not been analysed yet?',
  'Is the landing page ready to publish?',
  'Verify "Atlas Pro costs $59 per member per month."',
  'Which evidence sources are expiring?',
];

/** Renders **bold**, *italic* and "- " bullets; everything else is plain text (no HTML injection). */
function Rich({ text }: { text: string }) {
  const inline = (s: string, k: number) =>
    s.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, i) =>
      part.startsWith('**') ? <strong key={`${k}-${i}`}>{part.slice(2, -2)}</strong>
        : part.startsWith('*') && part.length > 2 ? <em key={`${k}-${i}`}>{part.slice(1, -1)}</em>
        : <React.Fragment key={`${k}-${i}`}>{part}</React.Fragment>);
  return (
    <div className="space-y-1.5">
      {text.split('\n').filter((l) => l.trim()).map((line, i) =>
        line.startsWith('- ')
          ? <p key={i} className="flex gap-1.5 pl-1"><span className="text-ink-400">•</span><span>{inline(line.slice(2), i)}</span></p>
          : <p key={i}>{inline(line, i)}</p>)}
    </div>
  );
}

export function Copilot({ brandId, brandName }: { brandId: string; brandName: string }) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTurns([]);
  }, [brandId]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns, busy]);

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || busy) return;
    setInput('');
    setError(null);
    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: 'user', content: question }]);
    setBusy(true);
    try {
      const result = await api.askCopilot(brandId, question, history);
      setTurns((t) => [...t, { role: 'assistant', content: result.answer, result }]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={cx('fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-navy-900 px-4 py-2.5 text-[13.5px] font-medium text-white shadow-lg shadow-navy-900/20 transition hover:bg-navy-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine-500', open && 'hidden')}
        aria-label="Open Governance Copilot"
      >
        <Bot className="h-4 w-4 text-teal-300" /> Ask Copilot
      </button>
      {open && (
        <aside className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[420px] flex-col border-l border-line bg-white shadow-2xl" aria-label="Governance Copilot">
          <header className="flex items-center gap-2.5 border-b border-line px-4 py-3">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-navy-900"><Bot className="h-4 w-4 text-teal-300" /></span>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-semibold text-ink-900">Governance Copilot</p>
              <p className="truncate text-[11.5px] text-ink-500">Read-only · answers from {brandName}'s records · cites every lookup</p>
            </div>
            <button onClick={() => setOpen(false)} className="rounded p-1.5 text-ink-500 hover:bg-ink-100" aria-label="Close Copilot"><X className="h-4 w-4" /></button>
          </header>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4 text-[13.5px] leading-relaxed">
            {turns.length === 0 && (
              <div>
                <p className="text-ink-600">Ask about risk, evidence, approvals or coverage. The Copilot looks things up with the same permissions you have and can't change anything.</p>
                <div className="mt-3 space-y-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => ask(s)} className="block w-full rounded-lg border border-line px-3 py-2 text-left text-[13px] text-ink-700 hover:border-pine-500 hover:bg-pine-50/50">{s}</button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((t, i) =>
              t.role === 'user' ? (
                <p key={i} className="ml-8 rounded-xl rounded-br-sm bg-navy-900 px-3 py-2 text-white">{t.content}</p>
              ) : (
                <div key={i} className="mr-4">
                  <div className="rounded-xl rounded-bl-sm border border-line bg-paper px-3 py-2.5 text-ink-800"><Rich text={t.content} /></div>
                  <p className="mt-1 text-[11px] text-ink-400">
                    {t.result.mode === 'claude' ? `Claude (${t.result.model ?? 'model'}) with ${t.result.trace.length} lookup(s)` : `Rule-based assistant · ${t.result.trace.length} lookup(s)`}
                  </p>
                  {t.result.notice && <p className="mt-1 text-[11.5px] text-amber-800">{t.result.notice}</p>}
                  {t.result.trace.length > 0 && (
                    <details className="mt-1 text-[12px]">
                      <summary className="flex cursor-pointer list-none items-center gap-1 font-medium text-pine-700"><ChevronDown className="h-3 w-3" /> How I found this</summary>
                      <ol className="mt-1.5 space-y-1.5">
                        {t.result.trace.map((s, k) => (
                          <li key={k} className="rounded-md border border-line bg-white px-2 py-1.5">
                            <p className="font-mono text-[11.5px] text-ink-700">{s.tool}({Object.keys(s.input).length ? JSON.stringify(s.input) : ''})</p>
                            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words text-[11px] text-ink-500">{JSON.stringify(s.output, null, 1).slice(0, 1800)}</pre>
                          </li>
                        ))}
                      </ol>
                    </details>
                  )}
                </div>
              ),
            )}
            {busy && <p className="text-[12.5px] text-ink-500">Looking that up…</p>}
            {error && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-[12.5px] text-red-800">{error}</p>}
            <div ref={endRef} />
          </div>

          <form onSubmit={(e) => { e.preventDefault(); ask(input); }} className="flex gap-2 border-t border-line p-3">
            <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} placeholder="Ask about risk, claims, approvals…"
              className="min-w-0 flex-1 rounded-lg border border-line px-3 py-2 text-[13.5px] focus:border-pine-500 focus:outline-none" aria-label="Question" />
            <button type="submit" disabled={busy || input.trim().length < 2} className="grid h-9 w-9 place-items-center rounded-lg bg-pine-600 text-white disabled:opacity-40" aria-label="Send"><Send className="h-4 w-4" /></button>
          </form>
        </aside>
      )}
    </>
  );
}
