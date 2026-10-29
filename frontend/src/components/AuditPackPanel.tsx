import { useCallback, useEffect, useState } from 'react';
import { Download, FileArchive } from 'lucide-react';
import { Button, cx, useToast } from './ui';
import { api, type AuditPack } from '../api';

const RESULT: Record<string, { label: string; cls: string }> = {
  pass: { label: 'Chain verified against previous export', cls: 'border-pine-200 bg-pine-50 text-pine-800' },
  pass_unanchored: { label: 'Chain recomputed · no earlier export to compare', cls: 'border-amber-200 bg-amber-50 text-amber-900' },
  incomplete: { label: 'Incomplete · malformed events', cls: 'border-amber-200 bg-amber-50 text-amber-900' },
  fail: { label: 'Verification failed', cls: 'border-red-200 bg-red-50 text-red-800' },
};

export function AuditPackPanel({ campaignId, canExport }: { campaignId: string; canExport: boolean }) {
  const toast = useToast();
  const [packs, setPacks] = useState<AuditPack[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!canExport) return;
    api.getAuditPacks(campaignId).then(setPacks).catch((e) => toast(e.message, 'error'));
  }, [campaignId, canExport, toast]);
  useEffect(() => {
    load();
  }, [load]);

  if (!canExport) return null;

  const create = async () => {
    setBusy(true);
    try {
      const p = await api.createAuditPack(campaignId);
      toast(`Audit pack exported (${p.event_count} events, ${RESULT[p.verification]?.label ?? p.verification}).`, p.verification === 'fail' ? 'error' : 'success');
      load();
    } catch (e: any) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const latest = packs?.[0];
  return (
    <div className="rounded-xl border border-line bg-white px-4 py-3 text-[13px]">
      <div className="flex flex-wrap items-center gap-3">
        <FileArchive className="h-4 w-4 text-ink-500" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink-900">Audit pack</p>
          <p className="text-[12px] text-ink-500">A PDF report and a JSON manifest built from one snapshot, with a SHA-256 hash chain over the assets’ audit events. Not digitally signed.</p>
        </div>
        <Button size="sm" variant="primary" disabled={busy} onClick={create}>{busy ? 'Exporting…' : 'Export audit pack'}</Button>
      </div>
      {latest && (
        <div className="mt-3 space-y-2 border-t border-line pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cx('rounded border px-1.5 py-px text-[11px] font-semibold', (RESULT[latest.verification] ?? RESULT.incomplete).cls)}>{(RESULT[latest.verification] ?? RESULT.incomplete).label}</span>
            <span className="text-[12px] text-ink-500">{latest.created_at.slice(0, 19).replace('T', ' ')} UTC · {latest.created_by} · {latest.asset_count} asset(s) · {latest.event_count} event(s)</span>
            <a className="ml-auto inline-flex items-center gap-1 text-pine-700 hover:underline" href={latest.pdf_url}><Download className="h-3.5 w-3.5" /> PDF</a>
            <a className="inline-flex items-center gap-1 text-pine-700 hover:underline" href={latest.json_url}><Download className="h-3.5 w-3.5" /> JSON</a>
          </div>
          <p className="text-[12px] text-ink-600">{latest.summary}</p>
          <p className="break-all font-mono text-[11px] text-ink-500">final chain {latest.final_chain_hash} · manifest {latest.manifest_sha256}</p>
          {latest.limitations.length > 0 && (
            <details className="text-[12px] text-ink-600">
              <summary className="cursor-pointer text-ink-700">{latest.limitations.length} limitation(s) disclosed in the pack</summary>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">{latest.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </details>
          )}
          {packs && packs.length > 1 && <p className="text-[11.5px] text-ink-400">{packs.length - 1} earlier export(s) kept; each new export is compared with the previous one.</p>}
        </div>
      )}
    </div>
  );
}
