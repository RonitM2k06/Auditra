import { useState } from 'react';
import { Button, Field, inputCls, Modal, useToast } from './ui';
import type { Brand } from '../types';
import { api } from '../api';

interface NewBrandModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (brand: Brand) => void;
}

export function NewBrandModal({ open, onClose, onCreated }: NewBrandModalProps) {
  const toast = useToast();
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) return;
    setSaving(true);
    try {
      const created = await api.createBrand({
        name: name.trim(),
        industry: industry.trim() || 'General',
        description: description.trim() || undefined,
        is_sample: false,
      });
      toast(`Created ${created.name}. Add a few rules to start reviewing.`, 'success');
      setName('');
      setIndustry('');
      setDescription('');
      onCreated(created);
      onClose();
    } catch (err: any) {
      toast(err.message || 'Could not create the workspace.', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New workspace"
      description="A workspace holds one brand's rulebook, content, and review history."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="new-brand-form" disabled={saving || name.trim().length < 2}>
            {saving ? 'Creating…' : 'Create workspace'}
          </Button>
        </>
      }
    >
      <form id="new-brand-form" onSubmit={submit} className="space-y-3">
        <Field label="Brand name" required>
          <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Health" autoFocus />
        </Field>
        <Field label="Industry">
          <input className={inputCls} value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="Healthcare" />
        </Field>
        <Field label="Description" hint="Optional. Helps reviewers understand the brand.">
          <textarea className={inputCls} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
      </form>
    </Modal>
  );
}
