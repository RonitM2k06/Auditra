import React, { useState } from 'react';
import { Building2, X } from 'lucide-react';
import { Brand } from '../types';
import { api } from '../api';

interface NewBrandModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBrandCreated: (brand: Brand) => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const NewBrandModal: React.FC<NewBrandModalProps> = ({
  isOpen,
  onClose,
  onBrandCreated,
  showToast,
}) => {
  const [name, setName] = useState('');
  const [industry, setIndustry] = useState('Technology');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    try {
      const created = await api.createBrand({
        name: name.trim(),
        industry,
        description: description.trim(),
        is_sample: false,
      });
      showToast(`Brand workspace '${created.name}' created`, 'success');
      onBrandCreated(created);
      onClose();
    } catch (err: any) {
      showToast(err.message || 'Error creating brand', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-surface-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-brand-500" />
            <h3 className="text-base font-bold text-dark-primary">Create Brand Workspace</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-dark-secondary mb-1">Brand Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Enterprise, Veloce Health"
              className="w-full p-2.5 border border-surface-border rounded-lg bg-surface-base focus:bg-white text-dark-primary"
            />
          </div>

          <div>
            <label className="block font-semibold text-dark-secondary mb-1">Industry Sector</label>
            <select
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="w-full p-2.5 border border-surface-border rounded-lg bg-white text-dark-primary"
            >
              <option value="Enterprise Cloud">Enterprise Cloud & Infrastructure</option>
              <option value="Financial Technology">Financial Services & FinTech</option>
              <option value="Healthcare & Bio">Healthcare & Life Sciences</option>
              <option value="E-Commerce & Retail">E-Commerce & Retail</option>
              <option value="Consumer Technology">Consumer Tech & Mobile</option>
              <option value="Automotive & Energy">Automotive & Energy</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-dark-secondary mb-1">Workspace Description</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Primary products, target audience, and brand mission..."
              className="w-full p-2.5 border border-surface-border rounded-lg bg-surface-base focus:bg-white text-dark-primary"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-dark-secondary hover:bg-surface-muted rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg font-semibold shadow-sm disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Workspace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
