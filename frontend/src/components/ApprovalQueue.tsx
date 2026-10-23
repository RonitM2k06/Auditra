import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  Clock,
  RotateCcw,
  XCircle,
  MessageSquare,
  ArrowRight,
  ShieldAlert,
  User,
  Send
} from 'lucide-react';
import { ContentItemDetail, Brand } from '../types';
import { api } from '../api';

interface ApprovalQueueProps {
  brand: Brand;
  userRole: 'creator' | 'reviewer' | 'admin';
  onOpenContent: (contentId: string) => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const ApprovalQueue: React.FC<ApprovalQueueProps> = ({
  brand,
  userRole,
  onOpenContent,
  showToast,
}) => {
  const [queueItems, setQueueItems] = useState<ContentItemDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<ContentItemDetail | null>(null);
  const [newComment, setNewComment] = useState('');
  const [decisionReason, setDecisionReason] = useState('');
  const [decisionMode, setDecisionMode] = useState<'approved' | 'changes_requested' | 'rejected' | null>(null);

  useEffect(() => {
    loadQueue();
  }, [brand.id]);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const items = await api.getContentItems(brand.id, 'in_review');
      // Fetch full details for each
      const detailed = await Promise.all(items.map((i) => api.getContentItem(i.id)));
      setQueueItems(detailed);
      if (detailed.length > 0 && !selectedItem) {
        setSelectedItem(detailed[0]);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load approval queue', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (decision: 'approved' | 'changes_requested' | 'rejected') => {
    if (!selectedItem) return;
    try {
      const updated = await api.recordDecision(selectedItem.id, {
        decision,
        reviewer_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Compliance Officer',
        reviewer_role: 'Brand Compliance Lead',
        comments: decisionReason,
      });
      showToast(`Review decision recorded: ${decision.replace('_', ' ').toUpperCase()}`, 'success');
      setDecisionMode(null);
      setDecisionReason('');
      loadQueue();
    } catch (err: any) {
      showToast(err.message || 'Error recording decision', 'error');
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem || !newComment.trim()) return;
    try {
      await api.addComment(selectedItem.id, {
        text: newComment,
        author_name: userRole === 'reviewer' ? 'Sarah Chen' : 'Alex Rivers',
        author_role: userRole === 'reviewer' ? 'Compliance Lead' : 'Content Creator',
      });
      const refreshed = await api.getContentItem(selectedItem.id);
      setSelectedItem(refreshed);
      setNewComment('');
      showToast('Comment added', 'info');
    } catch (err: any) {
      showToast(err.message || 'Error posting comment', 'error');
    }
  };

  return (
    <div className="flex-1 p-8 overflow-hidden flex flex-col space-y-6 bg-surface-base">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold text-dark-primary">Governance Approval Queue</h2>
          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800">
            {queueItems.length} Awaiting Decision
          </span>
        </div>
        <p className="text-xs text-dark-muted mt-0.5">
          Formal human-in-the-loop review. Only authorized reviewers can certify or request revisions.
        </p>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-xs text-dark-muted">
          Loading approval items...
        </div>
      ) : queueItems.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-12 bg-white rounded-xl border border-surface-border">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mb-3" />
          <h3 className="text-base font-bold text-dark-primary">Approval Queue is Clear</h3>
          <p className="text-xs text-dark-muted mt-1 max-w-sm">
            All submitted content reviews have been processed or are currently in draft revision.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex gap-6 overflow-hidden">
          {/* List column */}
          <div className="w-80 bg-white rounded-xl border border-surface-border p-3 overflow-y-auto space-y-2 shrink-0">
            {queueItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedItem?.id === item.id
                    ? 'border-brand-500 bg-brand-50/40 shadow-xs'
                    : 'border-surface-border hover:bg-surface-muted/60'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] uppercase font-bold text-slate-500">
                    {item.content_type.replace('_', ' ')}
                  </span>
                  <span className="text-xs font-mono text-dark-muted">v{item.current_version_number}</span>
                </div>
                <div className="text-xs font-bold text-dark-primary line-clamp-1 mb-1">{item.title}</div>
                <div className="text-[11px] text-dark-muted flex items-center justify-between">
                  <span>By {item.created_by}</span>
                  <span className="text-amber-700 font-semibold flex items-center gap-1">
                    <Clock className="w-3 h-3" /> In Review
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Detailed item inspector */}
          {selectedItem && (
            <div className="flex-1 bg-white rounded-xl border border-surface-border flex flex-col overflow-hidden shadow-xs">
              {/* Header */}
              <div className="p-4 border-b border-surface-border flex items-center justify-between bg-slate-50">
                <div>
                  <h3 className="text-sm font-bold text-dark-primary">{selectedItem.title}</h3>
                  <div className="text-xs text-dark-muted flex items-center gap-3 mt-0.5">
                    <span>Channel: {selectedItem.content_type.replace('_', ' ')}</span>
                    <span>•</span>
                    <span>Author: {selectedItem.created_by}</span>
                    <span>•</span>
                    <span>Revision: Version {selectedItem.current_version_number}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onOpenContent(selectedItem.id)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-surface-muted hover:bg-slate-200 text-dark-secondary rounded-lg text-xs font-semibold"
                  >
                    <span>Open in Studio</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>

                  {userRole === 'reviewer' && (
                    <div className="flex items-center gap-1 pl-2 border-l border-surface-border">
                      <button
                        onClick={() => setDecisionMode('approved')}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => setDecisionMode('changes_requested')}
                        className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow-xs"
                      >
                        Request Changes
                      </button>
                      <button
                        onClick={() => setDecisionMode('rejected')}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Body & Findings Overview */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-dark-muted mb-2">
                    Submitted Copy (Version {selectedItem.current_version_number})
                  </h4>
                  <div className="p-4 bg-surface-base rounded-xl border border-surface-border text-sm text-dark-primary leading-relaxed whitespace-pre-wrap font-sans">
                    {selectedItem.current_version?.body}
                  </div>
                </div>

                {/* Latest Scan Findings Summary */}
                {selectedItem.latest_review && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-dark-muted mb-2">
                      Automated Scan Findings ({selectedItem.latest_review.findings.length})
                    </h4>
                    <div className="space-y-2">
                      {selectedItem.latest_review.findings.map((f) => (
                        <div
                          key={f.id}
                          className="p-3 bg-white border border-surface-border rounded-lg text-xs flex items-start justify-between gap-3 shadow-xs"
                        >
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-bold text-dark-primary capitalize">
                                {f.category.replace('_', ' ')}
                              </span>
                              <span
                                className={`text-[10px] font-bold uppercase px-1.5 py-0.2 rounded ${
                                  f.severity === 'critical'
                                    ? 'bg-red-100 text-red-700'
                                    : f.severity === 'high'
                                    ? 'bg-amber-100 text-amber-700'
                                    : 'bg-blue-100 text-blue-700'
                                }`}
                              >
                                {f.severity}
                              </span>
                            </div>
                            <p className="text-dark-secondary">{f.explanation}</p>
                            {f.source_reference && (
                              <div className="text-[10px] text-dark-muted mt-1">Source: {f.source_reference}</div>
                            )}
                          </div>

                          <div className="text-right shrink-0">
                            <span className="font-mono text-slate-500">
                              {f.is_applied ? 'Fixed' : 'Unresolved'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Reviewer Comments & Feedback Thread */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-dark-muted mb-2">
                    Review Discussion & Change History
                  </h4>
                  <div className="space-y-2 mb-3">
                    {selectedItem.comments.length === 0 ? (
                      <div className="text-xs text-dark-muted italic">No comments added yet.</div>
                    ) : (
                      selectedItem.comments.map((c) => (
                        <div key={c.id} className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-dark-primary">{c.author_name} ({c.author_role})</span>
                            <span className="text-[10px] text-dark-muted">
                              {new Date(c.created_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-dark-secondary">{c.text}</p>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Add comment input */}
                  <form onSubmit={handleAddComment} className="flex gap-2">
                    <input
                      type="text"
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      placeholder="Add compliance notes or feedback..."
                      className="flex-1 text-xs p-2 border border-surface-border rounded-lg"
                    />
                    <button
                      type="submit"
                      disabled={!newComment.trim()}
                      className="px-3 py-2 bg-navy-900 hover:bg-navy-800 text-white rounded-lg text-xs font-semibold disabled:opacity-50 flex items-center gap-1"
                    >
                      <Send className="w-3 h-3" />
                      <span>Comment</span>
                    </button>
                  </form>
                </div>
              </div>

              {/* Decision Dialog */}
              {decisionMode && (
                <div className="p-4 bg-slate-50 border-t border-surface-border">
                  <h4 className="text-xs font-bold text-dark-primary mb-1 capitalize">
                    Confirm: {decisionMode.replace('_', ' ')}
                  </h4>
                  <textarea
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    placeholder="Enter formal justification or required edits for the author..."
                    rows={2}
                    className="w-full text-xs p-2 border border-surface-border rounded-lg bg-white mb-2"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setDecisionMode(null)}
                      className="px-3 py-1 text-xs text-dark-secondary hover:bg-slate-200 rounded"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleDecision(decisionMode)}
                      className="px-3 py-1 bg-navy-900 hover:bg-navy-800 text-white text-xs font-semibold rounded"
                    >
                      Submit Decision
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
