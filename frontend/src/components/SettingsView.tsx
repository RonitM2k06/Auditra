import React, { useState } from 'react';
import { Settings, Shield, Cpu, RotateCcw, Building2, Check, AlertCircle } from 'lucide-react';
import { Brand } from '../types';
import { api } from '../api';

interface SettingsViewProps {
  brand: Brand;
  onBrandUpdated: (brand: Brand) => void;
  onResetSample: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  brand,
  onBrandUpdated,
  onResetSample,
  showToast,
}) => {
  const [name, setName] = useState(brand.name);
  const [industry, setIndustry] = useState(brand.industry);
  const [description, setDescription] = useState(brand.description || '');
  const [primaryColor, setPrimaryColor] = useState(brand.primary_color);
  const [secondaryColor, setSecondaryColor] = useState(brand.secondary_color);
  const [saving, setSaving] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.createBrand({
        name,
        industry,
        description,
        primary_color: primaryColor,
        secondary_color: secondaryColor,
      });
      onBrandUpdated(updated);
      showToast('Brand settings updated', 'success');
    } catch (err: any) {
      showToast(err.message || 'Error updating settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-surface-base max-w-4xl">
      <div>
        <h2 className="text-xl font-bold text-dark-primary">Governance & Workspace Settings</h2>
        <p className="text-xs text-dark-muted mt-0.5">
          Configure brand identity metadata, engine parameters, and demonstration workspaces.
        </p>
      </div>

      {/* Brand Identity Form */}
      <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs">
        <h3 className="text-sm font-bold text-dark-primary mb-1">Brand Profile</h3>
        <p className="text-xs text-dark-muted mb-4">Organizational details used to contextualize governance rules</p>

        <form onSubmit={handleSave} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-dark-secondary mb-1">Brand Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full p-2 border border-surface-border rounded-lg bg-surface-base focus:bg-white text-dark-primary"
              />
            </div>
            <div>
              <label className="block font-semibold text-dark-secondary mb-1">Industry Sector</label>
              <input
                type="text"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full p-2 border border-surface-border rounded-lg bg-surface-base focus:bg-white text-dark-primary"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-dark-secondary mb-1">Brand Description</label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full p-2 border border-surface-border rounded-lg bg-surface-base focus:bg-white text-dark-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-dark-secondary mb-1">Primary Brand Accent</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-8 h-8 rounded border border-surface-border cursor-pointer p-0.5"
                />
                <span className="font-mono text-dark-muted">{primaryColor}</span>
              </div>
            </div>
            <div>
              <label className="block font-semibold text-dark-secondary mb-1">Secondary Brand Tone</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={secondaryColor}
                  onChange={(e) => setSecondaryColor(e.target.value)}
                  className="w-8 h-8 rounded border border-surface-border cursor-pointer p-0.5"
                />
                <span className="font-mono text-dark-muted">{secondaryColor}</span>
              </div>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
            >
              {saving ? 'Saving...' : 'Save Brand Settings'}
            </button>
          </div>
        </form>
      </div>

      {/* Engine Status & Disclosure */}
      <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-dark-primary mb-1">Compliance Engine & AI Transparency</h3>
        <p className="text-xs text-dark-muted">
          AUDITRA operates a multi-tier governance stack combining deterministic verification with optional LLM voice evaluation.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-4 bg-surface-base rounded-xl border border-surface-border space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-dark-primary">Deterministic Engine</span>
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded font-bold text-[10px]">
                ACTIVE
              </span>
            </div>
            <p className="text-dark-muted leading-relaxed">
              Regex and token offset evaluation for prohibited terms, preferred vocabulary, and mandatory disclosures. Zero hallucination risk.
            </p>
          </div>

          <div className="p-4 bg-surface-base rounded-xl border border-surface-border space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-dark-primary">AI Tone & Voice Assistant</span>
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded font-bold text-[10px]">
                HYBRID READY
              </span>
            </div>
            <p className="text-dark-muted leading-relaxed">
              Structured Pydantic schema validation. When API keys (Gemini/OpenAI/Claude) are omitted, gracefully falls back to deterministic analysis without disruption.
            </p>
          </div>
        </div>
      </div>

      {/* Reset Demo Workspace */}
      <div className="bg-white rounded-xl border border-red-200 p-6 shadow-xs flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-dark-primary">Reset Northstar Demo Data</h3>
          <p className="text-xs text-dark-muted mt-0.5">
            Restore the pre-configured Northstar brand workspace with 7 rules, 3 approved claims, and sample content.
          </p>
        </div>
        <button
          onClick={onResetSample}
          className="flex items-center gap-1.5 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-lg text-xs font-semibold transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Sample Workspace</span>
        </button>
      </div>
    </div>
  );
};
