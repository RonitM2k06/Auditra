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
  onClose: () => void;
  onSubmit: (note: string) => void;
}

/** Reviewer decision dialog. A note is required for anything other than approval. */
export function DecisionModal({ decision, busy, warning, onClose, onSubmit }: DecisionModalProps) {
  const [note, setNote] = useState('');
  useEffect(() => setNote(''), [decision]);
  if (!decision) return null;

  const meta = META[decision];
  const needsNote = decision !== 'approved';
  return (
    <Modal
      open
      onClose={onClose}
      title={meta.title}
      description={meta.body}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant={meta.variant} disabled={busy || (needsNote && !note.trim())} onClick={() => onSubmit(note.trim())}>
            {busy ? 'Saving…' : meta.label}
          </Button>
        </>
      }
    >
      {warning && <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] leading-relaxed text-amber-900">{warning}</div>}
      <Field label={needsNote ? 'Note to the author' : 'Note (optional)'} required={needsNote}>
        <textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} className={inputCls} autoFocus />
      </Field>
    </Modal>
  );
}
