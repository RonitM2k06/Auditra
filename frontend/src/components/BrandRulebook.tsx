import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  Upload,
  Search,
  CheckCircle,
  AlertCircle,
  FileText,
  Trash2,
  Edit2,
  ShieldCheck,
  Tag,
  Check
} from 'lucide-react';
import { BrandRule, ApprovedClaim, Brand } from '../types';
import { api } from '../api';

interface BrandRulebookProps {
  brand: Brand;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const BrandRulebook: React.FC<BrandRulebookProps> = ({ brand, showToast }) => {
  const [activeTab, setActiveTab] = useState<'rules' | 'claims'>('rules');
  const [rules, setRules] = useState<BrandRule[]>([]);
  const [claims, setClaims] = useState<ApprovedClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [search, setSearch] = useState('');

  // Modals
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showAddClaimModal, setShowAddClaimModal] = useState(false);

  // Form states
  const [newRule, setNewRule] = useState<Partial<BrandRule>>({
    name: '',
    category: 'prohibited_term',
    description: '',
    rule_text: '',
    match_pattern: '',
    suggested_replacement: '',
    severity: 'high',
    source_reference: '',
    is_active: true,
  });

  const [newClaim, setNewClaim] = useState<Partial<ApprovedClaim>>({
    claim_statement: '',
    topic: 'Performance',
    evidence_source: '',
    verification_date: new Date().toISOString().split('T')[0],
    is_active: true,
  });

  const [uploadFile, setUploadFile] = useState<File | null>(null);

  useEffect(() => {
    loadData();
  }, [brand.id]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rulesData, claimsData] = await Promise.all([
        api.getRules(brand.id),
        api.getClaims(brand.id),
      ]);
      setRules(rulesData);
      setClaims(claimsData);
    } catch (err: any) {
      showToast(err.message || 'Failed to load rulebook', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRuleActive = async (rule: BrandRule) => {
    try {
      const updated = await api.updateRule(brand.id, rule.id, { is_active: !rule.is_active });
      setRules(rules.map((r) => (r.id === rule.id ? updated : r)));
      showToast(`Rule '${rule.name}' ${updated.is_active ? 'activated' : 'deactivated'}`, 'info');
    } catch (err: any) {
      showToast(err.message || 'Error updating rule', 'error');
    }
  };

  const handleDeleteRule = async (ruleId: string, ruleName: string) => {
    if (!window.confirm(`Delete rule '${ruleName}'?`)) return;
    try {
      await api.deleteRule(brand.id, ruleId);
      setRules(rules.filter((r) => r.id !== ruleId));
      showToast('Rule deleted', 'info');
    } catch (err: any) {
      showToast(err.message || 'Error deleting rule', 'error');
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRule.name || !newRule.description || !newRule.rule_text) {
      showToast('Please fill in required fields', 'error');
      return;
    }
    try {
      const created = await api.createRule(brand.id, newRule);
      setRules([created, ...rules]);
      setShowAddRuleModal(false);
      setNewRule({
        name: '',
        category: 'prohibited_term',
        description: '',
        rule_text: '',
        match_pattern: '',
        suggested_replacement: '',
        severity: 'high',
        source_reference: '',
        is_active: true,
      });
      showToast(`Rule '${created.name}' successfully added`, 'success');
    } catch (err: any) {
      showToast(err.message || 'Error adding rule', 'error');
    }
  };

  const handleCreateClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClaim.claim_statement || !newClaim.evidence_source) {
      showToast('Please enter both claim statement and evidence source', 'error');
      return;
    }
    try {
      const created = await api.createClaim(brand.id, newClaim);
      setClaims([created, ...claims]);
      setShowAddClaimModal(false);
      setNewClaim({
        claim_statement: '',
        topic: 'Performance',
        evidence_source: '',
        verification_date: new Date().toISOString().split('T')[0],
        is_active: true,
      });
      showToast('Verified claim registered', 'success');
    } catch (err: any) {
      showToast(err.message || 'Error registering claim', 'error');
    }
  };

  const handleUploadGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      showToast('Please select a file to upload', 'error');
      return;
    }
    try {
      const res = await api.uploadGuidelines(brand.id, uploadFile);
      showToast(res.message || 'Guideline ingested', 'success');
      setShowUploadModal(false);
      setUploadFile(null);
      loadData();
    } catch (err: any) {
      showToast(err.message || 'Failed to ingest guideline', 'error');
    }
  };

  const filteredRules = rules.filter((r) => {
    if (categoryFilter !== 'all' && r.category !== categoryFilter) return false;
    if (
      search &&
      !r.name.toLowerCase().includes(search.toLowerCase()) &&
      !r.description.toLowerCase().includes(search.toLowerCase()) &&
      !(r.match_pattern && r.match_pattern.toLowerCase().includes(search.toLowerCase()))
    ) {
      return false;
    }
    return true;
  });

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-surface-base">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-dark-primary">Brand Rulebook & Claims Registry</h2>
            <span className="text-xs px-2 py-0.5 rounded bg-brand-50 text-brand-700 border border-brand-200 font-semibold">
              {rules.length} Rules Active
            </span>
          </div>
          <p className="text-xs text-dark-muted mt-0.5">
            Grounded brand policies governing tone, vocabulary, disclosures, and validated evidence.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-surface-border hover:bg-surface-muted text-dark-secondary rounded-lg text-xs font-semibold transition-colors shadow-xs"
          >
            <Upload className="w-3.5 h-3.5 text-slate-500" />
            <span>Ingest Guideline (.txt/.md)</span>
          </button>

          {activeTab === 'rules' ? (
            <button
              onClick={() => setShowAddRuleModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Add Brand Rule</span>
            </button>
          ) : (
            <button
              onClick={() => setShowAddClaimModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Register Approved Claim</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Tabs */}
      <div className="flex items-center gap-2 border-b border-surface-border">
        <button
          onClick={() => setActiveTab('rules')}
          className={`pb-2.5 px-3 text-xs font-bold transition-colors border-b-2 ${
            activeTab === 'rules'
              ? 'border-brand-500 text-brand-600'
              : 'border-transparent text-dark-muted hover:text-dark-primary'
          }`}
        >
          Governance Rules ({rules.length})
        </button>
        <button
          onClick={() => setActiveTab('claims')}
          className={`pb-2.5 px-3 text-xs font-bold transition-colors border-b-2 ${
            activeTab === 'claims'
              ? 'border-brand-500 text-brand-600'
              : 'border-transparent text-dark-muted hover:text-dark-primary'
          }`}
        >
          Approved Claims Registry ({claims.length})
        </button>
      </div>

      {activeTab === 'rules' ? (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-white rounded-xl border border-surface-border p-3.5 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-1 overflow-x-auto w-full sm:w-auto text-xs">
              {[
                { id: 'all', label: 'All Categories' },
                { id: 'prohibited_term', label: 'Prohibited' },
                { id: 'preferred_term', label: 'Preferred Term' },
                { id: 'required_phrase', label: 'Required Disclosures' },
                { id: 'restricted_claim', label: 'Restricted Claims' },
                { id: 'tone_voice', label: 'Tone & Voice' },
                { id: 'formatting_style', label: 'Style' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setCategoryFilter(tab.id)}
                  className={`px-2.5 py-1 rounded text-xs font-semibold whitespace-nowrap transition-colors ${
                    categoryFilter === tab.id
                      ? 'bg-navy-900 text-white'
                      : 'text-dark-muted hover:bg-surface-muted'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search rules..."
                className="w-full text-xs pl-8 pr-3 py-1.5 border border-surface-border rounded-lg bg-surface-base focus:bg-white focus:outline-none focus:border-brand-500 text-dark-primary"
              />
            </div>
          </div>

          {/* Rules Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredRules.map((rule) => {
              const severityBadges: Record<string, string> = {
                critical: 'bg-red-100 text-red-700',
                high: 'bg-amber-100 text-amber-700',
                medium: 'bg-blue-100 text-blue-700',
                low: 'bg-slate-100 text-slate-600',
              };

              return (
                <div
                  key={rule.id}
                  className={`bg-white rounded-xl border border-surface-border p-4 shadow-xs flex flex-col justify-between transition-all ${
                    !rule.is_active ? 'opacity-50 bg-slate-50' : ''
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <h4 className="text-sm font-bold text-dark-primary">{rule.name}</h4>
                        <div className="flex items-center gap-1.5 mt-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                            {rule.category.replace('_', ' ')}
                          </span>
                          <span
                            className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${
                              severityBadges[rule.severity]
                            }`}
                          >
                            {rule.severity}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleToggleRuleActive(rule)}
                          className={`text-xs px-2 py-0.5 rounded font-semibold transition-colors ${
                            rule.is_active
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {rule.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <button
                          onClick={() => handleDeleteRule(rule.id, rule.name)}
                          className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    <p className="text-xs text-dark-secondary mb-3 leading-relaxed">{rule.description}</p>

                    {/* Matched Pattern & Replacement */}
                    <div className="space-y-1.5 bg-surface-muted/70 p-2.5 rounded-lg text-xs mb-3 font-mono">
                      {rule.match_pattern && (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase font-bold text-slate-500 font-sans">Match:</span>
                          <span className="text-red-700 bg-red-50 px-1 py-0.2 rounded border border-red-200">
                            "{rule.match_pattern}"
                          </span>
                        </div>
                      )}
                      {rule.suggested_replacement && (
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase font-bold text-slate-500 font-sans">Suggests:</span>
                          <span className="text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200">
                            "{rule.suggested_replacement}"
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {rule.source_reference && (
                    <div className="pt-2 border-t border-slate-100 text-[11px] text-dark-muted flex items-center justify-between">
                      <span className="truncate">Ref: {rule.source_reference}</span>
                      <ShieldCheck className="w-3.5 h-3.5 text-brand-500 shrink-0" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Approved Claims Table */
        <div className="bg-white rounded-xl border border-surface-border shadow-xs overflow-hidden">
          <div className="p-4 border-b border-surface-border bg-slate-50 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-dark-primary">Substantiated Brand Claims</h3>
              <p className="text-xs text-dark-muted">
                Authoritative empirical facts and benchmark metrics verified by audit reports.
              </p>
            </div>
          </div>

          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-surface-border text-dark-muted uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Claim Statement</th>
                <th className="py-3 px-4">Topic</th>
                <th className="py-3 px-4">Authoritative Evidence Source</th>
                <th className="py-3 px-4">Verified Date</th>
                <th className="py-3 px-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {claims.map((claim) => (
                <tr key={claim.id} className="hover:bg-surface-muted/40 transition-colors">
                  <td className="py-3.5 px-4 font-medium text-dark-primary max-w-md">
                    {claim.claim_statement}
                  </td>
                  <td className="py-3.5 px-4 font-semibold text-slate-700">{claim.topic}</td>
                  <td className="py-3.5 px-4 text-dark-muted italic">{claim.evidence_source}</td>
                  <td className="py-3.5 px-4 text-dark-muted font-mono">{claim.verification_date || 'Current'}</td>
                  <td className="py-3.5 px-4 text-right">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      Verified
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Rule Modal */}
      {showAddRuleModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 border border-surface-border">
            <h3 className="text-base font-bold text-dark-primary mb-4">Add Configured Brand Rule</h3>
            <form onSubmit={handleCreateRule} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Rule Name *</label>
                <input
                  type="text"
                  required
                  value={newRule.name}
                  onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                  placeholder="e.g. Prohibit Unqualified Speed Multipliers"
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-dark-secondary mb-1">Category *</label>
                  <select
                    value={newRule.category}
                    onChange={(e: any) => setNewRule({ ...newRule, category: e.target.value })}
                    className="w-full p-2 border border-surface-border rounded-lg bg-white"
                  >
                    <option value="prohibited_term">Prohibited Term</option>
                    <option value="preferred_term">Preferred Term</option>
                    <option value="required_phrase">Required Phrase / Disclaimer</option>
                    <option value="restricted_claim">Restricted Claim</option>
                    <option value="tone_voice">Tone & Voice</option>
                    <option value="formatting_style">Formatting & Style</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-dark-secondary mb-1">Severity *</label>
                  <select
                    value={newRule.severity}
                    onChange={(e: any) => setNewRule({ ...newRule, severity: e.target.value })}
                    className="w-full p-2 border border-surface-border rounded-lg bg-white"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Rule Description / Rationale *</label>
                <textarea
                  required
                  rows={2}
                  value={newRule.description}
                  onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
                  placeholder="Why does this rule exist? What legal or brand impact does it mitigate?"
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-dark-secondary mb-1">Match Phrase / Pattern</label>
                  <input
                    type="text"
                    value={newRule.match_pattern}
                    onChange={(e) => setNewRule({ ...newRule, match_pattern: e.target.value })}
                    placeholder="e.g. 10x faster"
                    className="w-full p-2 border border-surface-border rounded-lg"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-dark-secondary mb-1">Suggested Replacement</label>
                  <input
                    type="text"
                    value={newRule.suggested_replacement}
                    onChange={(e) => setNewRule({ ...newRule, suggested_replacement: e.target.value })}
                    placeholder="e.g. accelerated throughput"
                    className="w-full p-2 border border-surface-border rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Source Reference Citation</label>
                <input
                  type="text"
                  value={newRule.source_reference}
                  onChange={(e) => setNewRule({ ...newRule, source_reference: e.target.value })}
                  placeholder="e.g. Northstar Legal Policy §4.2"
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Full Rule Directive *</label>
                <textarea
                  required
                  rows={2}
                  value={newRule.rule_text}
                  onChange={(e) => setNewRule({ ...newRule, rule_text: e.target.value })}
                  placeholder="Complete rule specification text..."
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddRuleModal(false)}
                  className="px-3 py-1.5 text-dark-secondary hover:bg-surface-muted rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg font-semibold"
                >
                  Save Brand Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Upload Guideline Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-surface-border">
            <h3 className="text-base font-bold text-dark-primary mb-2">Ingest Brand Guideline Document</h3>
            <p className="text-xs text-dark-muted mb-4">
              Upload a plain text or Markdown (.md, .txt) brand guide. AUDITRA's ingestion parser will extract structured rules and terminology.
            </p>

            <form onSubmit={handleUploadGuideline} className="space-y-4 text-xs">
              <div className="border-2 border-dashed border-surface-border rounded-xl p-6 text-center hover:bg-surface-muted/50 transition-colors">
                <input
                  type="file"
                  accept=".txt,.md"
                  onChange={(e) => setUploadFile(e.target.files ? e.target.files[0] : null)}
                  className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
                />
              </div>

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-3 py-1.5 text-dark-secondary hover:bg-surface-muted rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!uploadFile}
                  className="px-4 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg font-semibold disabled:opacity-50"
                >
                  Ingest & Parse
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Claim Modal */}
      {showAddClaimModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-surface-border">
            <h3 className="text-base font-bold text-dark-primary mb-2">Register Verified Claim</h3>
            <p className="text-xs text-dark-muted mb-4">
              Add a legally corroborated benchmark or product statistic to prevent false unverified claim flags.
            </p>

            <form onSubmit={handleCreateClaim} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Claim Statement *</label>
                <textarea
                  required
                  rows={2}
                  value={newClaim.claim_statement}
                  onChange={(e) => setNewClaim({ ...newClaim, claim_statement: e.target.value })}
                  placeholder="e.g. Northstar reduces cloud infrastructure idle spend by 28%."
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Topic</label>
                <input
                  type="text"
                  value={newClaim.topic}
                  onChange={(e) => setNewClaim({ ...newClaim, topic: e.target.value })}
                  placeholder="e.g. Cost Optimization, Security, SLA"
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div>
                <label className="block font-semibold text-dark-secondary mb-1">Evidence Source *</label>
                <input
                  type="text"
                  required
                  value={newClaim.evidence_source}
                  onChange={(e) => setNewClaim({ ...newClaim, evidence_source: e.target.value })}
                  placeholder="e.g. Q2 2026 Audit by Independent CloudLab"
                  className="w-full p-2 border border-surface-border rounded-lg"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddClaimModal(false)}
                  className="px-3 py-1.5 text-dark-secondary hover:bg-surface-muted rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg font-semibold"
                >
                  Register Claim
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
