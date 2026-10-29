import React, { useEffect, useState } from 'react';
import { Button, Field, inputCls, Modal } from './ui';

export type Decision = 'approved' | 'changes_requested' | 'rejected';

const META: Record<Decision, { title: string; body: string; label: string; variant: 'accent' | 'primary' | 'dangerSolid' }> = {
  approved: {
    title: 'Approve for publication',
    body: 'The approval is recorded against the current version with your name and the time. It does not change the text.',
    label: 'Approve',
    variant: 'accent',
  },
  changes_requested: {
    title: 'Request changes',
    body: 'The piece goes back to the author. Tell them what needs to change.',
    label: 'Request changes',
    variant: 'primary',
  },
  rejected: {
    title: 'Reject',
    body: 'Use this when the piece should not be published in any form. The author can start a new revision.',
    label: 'Reject',
    variant: 'dangerSolid',
  },
};

interface DecisionModalProps {
  decision: Decision | null;
  busy: boolean;
  warning?: React.ReactNode;
  version?: number;
  evidencePrompt?: boolean;
  onClose: () => void;
  onSubmit: (note: string, evidenceConfirmed: boolean) => void;
}

/** Reviewer decision dialog. A note is required for anything other than approval. */
export function DecisionModal({ decision, busy, warning, version, evidencePrompt, onClose, onSubmit }: DecisionModalProps) {
  const [note, setNote] = useState('');
  const [evidence, setEvidence] = useState(false);
  useEffect(() => {
    setNote('');
    setEvidence(false);
  }, [decision]);
  if (!decision) return null;

  const meta = META[decision];
  const needsNote = decision !== 'approved';
  return (
    <Modal
      open
      onClose={onClose}
      title={version ? `${meta.title} · v${version}` : meta.title}
      description={meta.body}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant={meta.variant} disabled={busy || (needsNote && !note.trim())} onClick={() => onSubmit(note.trim(), evidence)}>
            {busy ? 'Saving…' : meta.label}
          </Button>
        </>
      }
    >
      {warning && <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] leading-relaxed text-amber-900">{warning}</div>}
      {decision === 'approved' && (
        <label className="mb-3 flex items-start gap-2 rounded-md border border-line px-3 py-2.5 text-[13px] text-ink-800">
          <input type="checkbox" checked={evidence} onChange={(e) => setEvidence(e.target.checked)} className="mt-0.5 accent-pine-600" />
          <span>
            I reviewed the claim evidence for this version.
            <span className="block text-[12px] text-ink-500">
              {evidencePrompt ? 'Some claims are not fully supported. Policies may require this confirmation.' : 'Recorded with your approval and shown in the audit trail.'}
            </span>
          </span>
        </label>
      )}
      <Field label={needsNote ? 'Note to the author' : 'Note (optional)'} required={needsNote}>
        <textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} className={inputCls} autoFocus />
      </Field>
    </Modal>
  );
}
