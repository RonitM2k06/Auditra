import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Save,
  Send,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  AlertCircle,
  Check,
  RotateCcw,
  Clock,
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  MessageSquare,
  ChevronRight,
  ExternalLink,
  Edit3
} from 'lucide-react';
import { ContentItemDetail, Finding, ReviewRun } from '../types';
import { api } from '../api';

interface ReviewStudioProps {
  contentId: string | null;
  brandId: string;
  userRole: 'creator' | 'reviewer' | 'admin';
  onReviewCompleted?: () => void;
  onNavigateToReviews?: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const ReviewStudio: React.FC<ReviewStudioProps> = ({
  contentId,
  brandId,
  userRole,
  onReviewCompleted,
  onNavigateToReviews,
  showToast,
}) => {
  const [contentItem, setContentItem] = useState<ContentItemDetail | null>(null);
  const [title, setTitle] = useState('');
  const [contentType, setContentType] = useState('social_post');
  const [body, setBody] = useState('');
  const [savedBody, setSavedBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [editingCorrection, setEditingCorrection] = useState<{ findingId: string; text: string } | null>(null);
  const [reviewerComment, setReviewerComment] = useState('');
  const [showDecisionModal, setShowDecisionModal] = useState<'approved' | 'changes_requested' | 'rejected' | null>(null);

  // Load content
  useEffect(() => {
    if (contentId) {
      loadContent(contentId);
    } else {
      // New review initial state
      setTitle('New Promotional Content');
      setContentType('social_post');
      setBody('Northstar guarantees results for every customer. Our users will double their performance in seven days. Join today and unlock the unbelievable secret to instant cloud speed!!!');
      setSavedBody('');
      setContentItem(null);
    }
  }, [contentId]);

  const loadContent = async (id: string) => {
    setLoading(true);
    try {
      const data = await api.getContentItem(id);
      setContentItem(data);
      setTitle(data.title);
      setContentType(data.content_type);
      const currentBody = data.current_version?.body || '';
      setBody(currentBody);
      setSavedBody(currentBody);
    } catch (err: any) {
      showToast(err.message || 'Failed to load content', 'error');
    } finally {
      setLoading(false);
    }
  };

  const hasUnsavedChanges = body !== savedBody;
  const wordCount = body.trim() ? body.trim().split(/\s+/).length : 0;
  const charCount = body.length;

  // Save Draft
  const handleSaveDraft = async () => {
    if (!title.trim() || !body.trim()) {
      showToast('Title and content body cannot be empty', 'error');
      return;
    }

    setLoading(true);
    try {
      if (contentItem) {
        const updated = await api.updateContentItem(contentItem.id, {
          title,
          content_type: contentType,
          body,
          change_summary: 'Manual edits saved in editor',
          actor_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
          actor_role: userRole === 'reviewer' ? 'Compliance Lead' : 'Content Creator',
        });
        setContentItem(updated);
        setSavedBody(body);
        showToast('Draft version saved successfully', 'success');
      } else {
        const created = await api.createContentItem(brandId, {
          title,
          content_type: contentType,
          body,
          created_by: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
        });
        setContentItem(created);
        setSavedBody(body);
        showToast('New content item created', 'success');
      }
    } catch (err: any) {
      showToast(err.message || 'Error saving content', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Run Review
  const handleRunReview = async () => {
    if (!body.trim()) {
      showToast('Cannot analyze empty content', 'error');
      return;
    }

    setAnalyzing(true);
    try {
      let activeItemId = contentItem?.id;
      // Auto-save if unsaved or new
      if (!activeItemId || hasUnsavedChanges) {
        if (!activeItemId) {
          const created = await api.createContentItem(brandId, {
            title,
            content_type: contentType,
            body,
            created_by: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
          });
          activeItemId = created.id;
          setContentItem(created);
        } else {
          const updated = await api.updateContentItem(activeItemId, {
            title,
            content_type: contentType,
            body,
            change_summary: 'Auto-saved prior to review run',
            actor_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
          });
          setContentItem(updated);
        }
        setSavedBody(body);
      }

      const run = await api.runReview(activeItemId, {
        actor_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
        actor_role: userRole === 'reviewer' ? 'Compliance Lead' : 'Content Creator',
      });

      // Reload content details
      const refreshed = await api.getContentItem(activeItemId);
      setContentItem(refreshed);
      showToast(`Review complete: Risk score ${run.risk_score}/100 with ${run.findings.length} findings`, 'info');
      if (onReviewCompleted) onReviewCompleted();
    } catch (err: any) {
      showToast(err.message || 'Review failed', 'error');
    } finally {
      setAnalyzing(false);
    }
  };

  // Apply targeted correction
  const handleApplyCorrection = async (finding: Finding, customText?: string) => {
    setLoading(true);
    try {
      const updated = await api.applyCorrection(finding.id, {
        custom_replacement: customText,
        actor_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
        actor_role: userRole === 'reviewer' ? 'Compliance Lead' : 'Content Creator',
      });
      setContentItem(updated);
      const newBody = updated.current_version?.body || '';
      setBody(newBody);
      setSavedBody(newBody);
      setEditingCorrection(null);
      showToast(`Targeted correction applied. Created Version ${updated.current_version_number}`, 'success');
      // Automatically re-run compliance scan on the new version!
      await api.runReview(updated.id, {
        actor_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
      });
      const rechecked = await api.getContentItem(updated.id);
      setContentItem(rechecked);
    } catch (err: any) {
      showToast(err.message || 'Failed to apply correction', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Dismiss finding
  const handleDismissFinding = async (finding: Finding) => {
    try {
      await api.dismissFinding(finding.id, userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers');
      if (contentItem) {
        const refreshed = await api.getContentItem(contentItem.id);
        setContentItem(refreshed);
      }
      showToast('Finding dismissed from active review', 'info');
    } catch (err: any) {
      showToast(err.message || 'Error dismissing finding', 'error');
    }
  };

  // Submit for Review
  const handleSubmitForReview = async () => {
    if (!contentItem) return;
    setLoading(true);
    try {
      const updated = await api.submitForReview(
        contentItem.id,
        userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
        userRole === 'reviewer' ? 'Compliance Lead' : 'Content Creator'
      );
      setContentItem(updated);
      showToast('Submitted to Governance Approval Queue', 'success');
    } catch (err: any) {
      showToast(err.message || 'Submission failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Record Decision
  const handleRecordDecision = async (decision: 'approved' | 'changes_requested' | 'rejected') => {
    if (!contentItem) return;
    setLoading(true);
    try {
      const updated = await api.recordDecision(contentItem.id, {
        decision,
        reviewer_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Lead Reviewer',
        reviewer_role: 'Brand Compliance Lead',
        comments: reviewerComment,
      });
      setContentItem(updated);
      setShowDecisionModal(null);
      setReviewerComment('');
      showToast(`Decision recorded: ${decision.replace('_', ' ').toUpperCase()}`, 'success');
    } catch (err: any) {
      showToast(err.message || 'Failed to record decision', 'error');
    } finally {
      setLoading(false);
    }
  };

  const latestReview: ReviewRun | undefined = contentItem?.latest_review;
  const activeFindings = latestReview?.findings?.filter((f) => !f.is_dismissed) || [];

  const filteredFindings = activeFindings.filter((f) => {
    if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
    if (categoryFilter !== 'all' && f.category !== categoryFilter) return false;
    return true;
  });

  const riskScore = latestReview?.risk_score ?? 0;
  const getRiskColor = (score: number) => {
    if (score === 0) return 'text-emerald-600 bg-emerald-50 border-emerald-200';
    if (score < 30) return 'text-blue-600 bg-blue-50 border-blue-200';
    if (score < 60) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-red-600 bg-red-50 border-red-200';
  };

  const statusBadges: Record<string, { label: string; bg: string; text: string }> = {
    draft: { label: 'Draft', bg: 'bg-slate-100', text: 'text-slate-700' },
    in_review: { label: 'In Review', bg: 'bg-blue-100', text: 'text-blue-800' },
    changes_requested: { label: 'Changes Requested', bg: 'bg-amber-100', text: 'text-amber-800' },
    approved: { label: 'Approved', bg: 'bg-emerald-100', text: 'text-emerald-800' },
    rejected: { label: 'Rejected', bg: 'bg-red-100', text: 'text-red-800' },
  };

  const currentStatusInfo = statusBadges[contentItem?.status || 'draft'];

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)] overflow-hidden bg-surface-base">
      {/* Studio Header Bar */}
      <div className="bg-white border-b border-surface-border px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="text-base font-bold text-dark-primary bg-transparent hover:bg-slate-50 focus:bg-white px-2 py-1 rounded border border-transparent focus:border-brand-500 focus:outline-none transition-colors w-80 md:w-96"
            placeholder="Content Campaign Title..."
          />
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${currentStatusInfo.bg} ${currentStatusInfo.text}`}>
              {currentStatusInfo.label}
            </span>
            {contentItem && (
              <span className="text-xs font-medium text-dark-muted px-2 py-0.5 bg-surface-muted rounded">
                v{contentItem.current_version_number}
              </span>
            )}
            {hasUnsavedChanges && (
              <span className="text-xs text-amber-600 font-medium flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> Unsaved edits
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleSaveDraft}
            disabled={loading || analyzing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-surface-border hover:bg-surface-muted text-dark-secondary rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Draft</span>
          </button>

          <button
            onClick={handleRunReview}
            disabled={analyzing || loading}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{analyzing ? 'Scanning Compliance...' : 'Run Review'}</span>
          </button>

          {/* Workflow Transitions */}
          {contentItem?.status !== 'approved' && contentItem?.status !== 'in_review' && (
            <button
              onClick={handleSubmitForReview}
              disabled={loading || analyzing}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-navy-900 hover:bg-navy-800 text-white rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Submit for Review</span>
            </button>
          )}

          {userRole === 'reviewer' && contentItem?.status === 'in_review' && (
            <div className="flex items-center gap-1.5 pl-2 border-l border-surface-border">
              <button
                onClick={() => setShowDecisionModal('approved')}
                className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Approve</span>
              </button>
              <button
                onClick={() => setShowDecisionModal('changes_requested')}
                className="flex items-center gap-1 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Request Changes</span>
              </button>
              <button
                onClick={() => setShowDecisionModal('rejected')}
                className="flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Review Studio Workspace: Dual/Tri Pane */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Editor */}
        <div className="flex-1 flex flex-col bg-white border-r border-surface-border overflow-hidden">
          {/* Editor Meta Bar */}
          <div className="px-6 py-2.5 bg-surface-muted/60 border-b border-surface-border flex items-center justify-between text-xs text-dark-muted">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-dark-secondary">Channel:</span>
                <select
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value)}
                  className="bg-white border border-surface-border rounded px-2 py-0.5 text-xs text-dark-primary focus:outline-none focus:border-brand-500"
                >
                  <option value="social_post">Social Post</option>
                  <option value="advertisement">Advertisement</option>
                  <option value="email">Email Campaign</option>
                  <option value="landing_page">Landing Page</option>
                  <option value="announcement">Announcement</option>
                  <option value="blog_post">Case Study / Blog</option>
                </select>
              </div>

              {contentItem?.versions && contentItem.versions.length > 1 && (
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-dark-secondary">History:</span>
                  <span className="text-dark-muted">{contentItem.versions.length} checkpoints recorded</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 font-mono">
              <span>{wordCount} words</span>
              <span>•</span>
              <span>{charCount} chars</span>
            </div>
          </div>

          {/* Editor Content Area */}
          <div className="flex-1 p-6 overflow-y-auto">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Paste or write your marketing or corporate copy here to evaluate against active brand guidelines..."
              className="w-full h-full resize-none font-sans text-base text-dark-primary leading-relaxed focus:outline-none placeholder:text-slate-400"
            />
          </div>

          {/* Quick Guidance Footer */}
          <div className="px-6 py-2 bg-slate-50 border-t border-surface-border flex items-center justify-between text-xs text-dark-muted">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-brand-500" />
              <span>Evidence-First Governance: Findings reference configured Northstar brand policies.</span>
            </div>
            {latestReview && (
              <span className="text-[11px] font-mono text-slate-500">
                Engine: {latestReview.engine_type} • AI Status: {latestReview.ai_status}
              </span>
            )}
          </div>
        </div>

        {/* Right Pane: Governance Findings & Score */}
        <div className="w-96 md:w-[420px] bg-surface-base flex flex-col border-l border-surface-border overflow-hidden shrink-0">
          {/* Assessment Header Card */}
          <div className="p-4 bg-white border-b border-surface-border">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-dark-muted">Brand Health Assessment</span>
              {latestReview && (
                <span className={`px-2 py-0.5 text-xs font-bold rounded border ${getRiskColor(riskScore)}`}>
                  Risk Score: {riskScore}/100
                </span>
              )}
            </div>

            {latestReview ? (
              <div>
                <p className="text-xs text-dark-secondary mb-3 leading-snug">{latestReview.summary}</p>
                {/* Severity Breakdown Bar */}
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                  <div className="p-1.5 rounded bg-red-50 border border-red-100">
                    <div className="font-bold text-red-600">{latestReview.severity_counts.critical || 0}</div>
                    <div className="text-[10px] text-red-700 uppercase font-medium">Critical</div>
                  </div>
                  <div className="p-1.5 rounded bg-amber-50 border border-amber-100">
                    <div className="font-bold text-amber-600">{latestReview.severity_counts.high || 0}</div>
                    <div className="text-[10px] text-amber-700 uppercase font-medium">High</div>
                  </div>
                  <div className="p-1.5 rounded bg-blue-50 border border-blue-100">
                    <div className="font-bold text-blue-600">{latestReview.severity_counts.medium || 0}</div>
                    <div className="text-[10px] text-blue-700 uppercase font-medium">Medium</div>
                  </div>
                  <div className="p-1.5 rounded bg-slate-50 border border-slate-200">
                    <div className="font-bold text-slate-600">{latestReview.severity_counts.low || 0}</div>
                    <div className="text-[10px] text-slate-500 uppercase font-medium">Low</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-dark-muted text-center py-2">
                Click <b>Run Review</b> to scan copy against active brand rules and evidence.
              </div>
            )}
          </div>

          {/* Findings Filter Bar */}
          <div className="px-4 py-2 bg-slate-100 border-b border-surface-border flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-dark-secondary">Findings:</span>
              <span className="font-bold text-brand-600">
                {activeFindings.length} Active
              </span>
            </div>

            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-white border border-surface-border rounded px-2 py-0.5 text-xs text-dark-secondary focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Only</option>
              <option value="high">High Only</option>
              <option value="medium">Medium Only</option>
              <option value="low">Low Only</option>
            </select>
          </div>

          {/* Findings List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {filteredFindings.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-dark-muted">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mb-2" />
                <h4 className="text-sm font-bold text-dark-primary">No Governance Violations</h4>
                <p className="text-xs text-dark-muted mt-1">
                  {latestReview
                    ? 'Content is fully compliant with configured brand rules and approved claims.'
                    : 'Run a review scan to generate actionable findings.'}
                </p>
              </div>
            ) : (
              filteredFindings.map((finding) => {
                const isCrit = finding.severity === 'critical';
                const isHigh = finding.severity === 'high';
                const isMed = finding.severity === 'medium';

                const borderCls = isCrit
                  ? 'border-l-4 border-l-red-500'
                  : isHigh
                  ? 'border-l-4 border-l-amber-500'
                  : isMed
                  ? 'border-l-4 border-l-blue-500'
                  : 'border-l-4 border-l-slate-400';

                return (
                  <div
                    key={finding.id}
                    className={`bg-white rounded-lg border border-surface-border p-3.5 shadow-sm transition-all ${borderCls} ${
                      finding.is_applied ? 'opacity-50' : ''
                    }`}
                  >
                    {/* Header: Severity & Category */}
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-700">
                        {finding.category.replace('_', ' ')}
                      </span>
                      <span
                        className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                          isCrit
                            ? 'bg-red-100 text-red-700'
                            : isHigh
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {finding.severity}
                      </span>
                    </div>

                    {/* Matched text */}
                    <div className="mb-2">
                      <span className="text-xs font-semibold text-dark-secondary">Flagged Text: </span>
                      <code className="text-xs px-1.5 py-0.5 rounded bg-red-50 text-red-700 font-mono font-semibold">
                        "{finding.matched_text}"
                      </code>
                    </div>

                    {/* Explanation */}
                    <p className="text-xs text-dark-secondary leading-snug mb-2">{finding.explanation}</p>

                    {/* Citation / Source Reference */}
                    {finding.source_reference && (
                      <div className="text-[11px] text-dark-muted bg-surface-muted px-2 py-1 rounded mb-2.5 flex items-center gap-1">
                        <span className="font-semibold text-slate-600">Source:</span>
                        <span className="truncate">{finding.source_reference}</span>
                      </div>
                    )}

                    {/* Suggested Correction Box */}
                    {finding.suggested_correction && !finding.is_applied && (
                      <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-md p-2.5 mb-2.5">
                        <div className="flex items-center justify-between mb-1 text-[11px] font-semibold text-emerald-900">
                          <span>Targeted Recommendation:</span>
                          <button
                            onClick={() =>
                              setEditingCorrection(
                                editingCorrection?.findingId === finding.id
                                  ? null
                                  : { findingId: finding.id, text: finding.suggested_correction || '' }
                              )
                            }
                            className="text-emerald-700 hover:text-emerald-900 text-[10px] flex items-center gap-0.5"
                          >
                            <Edit3 className="w-2.5 h-2.5" />
                            {editingCorrection?.findingId === finding.id ? 'Cancel' : 'Edit'}
                          </button>
                        </div>

                        {editingCorrection?.findingId === finding.id ? (
                          <div className="space-y-2 mt-1">
                            <input
                              type="text"
                              value={editingCorrection.text}
                              onChange={(e) =>
                                setEditingCorrection({ ...editingCorrection, text: e.target.value })
                              }
                              className="w-full text-xs p-1.5 border border-emerald-300 rounded bg-white text-dark-primary focus:outline-none"
                            />
                            <button
                              onClick={() => handleApplyCorrection(finding, editingCorrection.text)}
                              className="w-full py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold"
                            >
                              Apply Custom Replacement
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-emerald-800 break-words pr-2">
                              {finding.suggested_correction}
                            </span>
                            <button
                              onClick={() => handleApplyCorrection(finding)}
                              disabled={loading}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold shadow-xs flex items-center gap-1 shrink-0 transition-colors"
                            >
                              <Check className="w-3 h-3" />
                              <span>Apply</span>
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Footer Actions */}
                    <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-xs">
                      {finding.is_applied ? (
                        <span className="text-emerald-700 font-semibold flex items-center gap-1 text-[11px]">
                          <Check className="w-3 h-3" /> Fixed in Version {contentItem?.current_version_number}
                        </span>
                      ) : (
                        <button
                          onClick={() => handleDismissFinding(finding)}
                          className="text-[11px] text-slate-400 hover:text-slate-600 transition-colors"
                        >
                          Dismiss Finding
                        </button>
                      )}

                      <span className="text-[10px] text-slate-400">
                        {finding.finding_source === 'deterministic' ? 'Deterministic Engine' : 'AI Grounded'}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Decision Modal for Reviewer */}
      {showDecisionModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 border border-surface-border">
            <h3 className="text-base font-bold text-dark-primary capitalize mb-2">
              Record Decision: {showDecisionModal.replace('_', ' ')}
            </h3>
            <p className="text-xs text-dark-muted mb-4">
              {showDecisionModal === 'approved'
                ? 'Approving this content certifies that all claims and rules have been verified for public release.'
                : showDecisionModal === 'changes_requested'
                ? 'Specify the required revisions for the creator before resubmission.'
                : 'Rejection marks this draft as non-viable under current brand policies.'}
            </p>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-dark-secondary mb-1">
                Reviewer Comments & Feedback:
              </label>
              <textarea
                value={reviewerComment}
                onChange={(e) => setReviewerComment(e.target.value)}
                placeholder="Enter formal justification or feedback for the creator..."
                rows={4}
                className="w-full text-xs p-2.5 border border-surface-border rounded-lg text-dark-primary focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowDecisionModal(null)}
                className="px-3 py-1.5 text-xs text-dark-secondary hover:bg-surface-muted rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={() => handleRecordDecision(showDecisionModal)}
                disabled={loading}
                className={`px-4 py-1.5 text-xs font-semibold text-white rounded-lg shadow-sm ${
                  showDecisionModal === 'approved'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : showDecisionModal === 'changes_requested'
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                Confirm {showDecisionModal.replace('_', ' ')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
