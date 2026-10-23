import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, Trash2, ArrowUpRight, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { ContentItem, Brand } from '../types';
import { api } from '../api';

interface ContentReviewsListProps {
  brand: Brand;
  onOpenContent: (contentId: string) => void;
  onNewReview: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const ContentReviewsList: React.FC<ContentReviewsListProps> = ({
  brand,
  onOpenContent,
  onNewReview,
  showToast,
}) => {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    loadItems();
  }, [brand.id, statusFilter]);

  const loadItems = async () => {
    setLoading(true);
    try {
      const data = await api.getContentItems(brand.id, statusFilter === 'all' ? undefined : statusFilter);
      setItems(data);
    } catch (err: any) {
      showToast(err.message || 'Failed to load content list', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete '${title}'? This action cannot be undone.`)) {
      return;
    }
    try {
      await api.deleteContentItem(id);
      showToast('Content item deleted', 'info');
      loadItems();
    } catch (err: any) {
      showToast(err.message || 'Error deleting item', 'error');
    }
  };

  const filtered = items.filter((item) =>
    item.title.toLowerCase().includes(search.toLowerCase()) ||
    item.created_by.toLowerCase().includes(search.toLowerCase())
  );

  const filterTabs = [
    { id: 'all', label: 'All Reviews' },
    { id: 'in_review', label: 'In Review' },
    { id: 'changes_requested', label: 'Changes Requested' },
    { id: 'approved', label: 'Approved' },
    { id: 'draft', label: 'Drafts' },
  ];

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-surface-base">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-dark-primary">Content Reviews</h2>
          <p className="text-xs text-dark-muted">
            Inspect, edit, and track governance approvals across all marketing campaigns.
          </p>
        </div>

        <button
          onClick={onNewReview}
          className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Content Review</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-xl border border-surface-border p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto w-full sm:w-auto">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                statusFilter === tab.id
                  ? 'bg-brand-500 text-white'
                  : 'text-dark-muted hover:bg-surface-muted hover:text-dark-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search reviews..."
            className="w-full text-xs pl-8 pr-3 py-1.5 border border-surface-border rounded-lg bg-surface-base focus:bg-white focus:outline-none focus:border-brand-500 text-dark-primary"
          />
        </div>
      </div>

      {/* Content Table */}
      <div className="bg-white rounded-xl border border-surface-border shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-dark-muted">Loading content reviews...</div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-xs text-dark-muted">
            No content reviews found matching the selected criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-surface-border bg-slate-50 text-dark-muted uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Channel</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Version</th>
                  <th className="py-3 px-4">Author</th>
                  <th className="py-3 px-4">Reviewer</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {filtered.map((item) => {
                  const statusColors: Record<string, string> = {
                    draft: 'bg-slate-100 text-slate-700',
                    in_review: 'bg-blue-100 text-blue-800',
                    changes_requested: 'bg-amber-100 text-amber-800',
                    approved: 'bg-emerald-100 text-emerald-800',
                    rejected: 'bg-red-100 text-red-800',
                  };
                  return (
                    <tr
                      key={item.id}
                      onClick={() => onOpenContent(item.id)}
                      className="hover:bg-surface-muted/50 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4 font-semibold text-dark-primary">
                        <div className="flex items-center gap-1.5">
                          <span>{item.title}</span>
                          <ArrowUpRight className="w-3 h-3 text-slate-400 shrink-0" />
                        </div>
                      </td>
                      <td className="py-3.5 px-4 capitalize text-dark-muted">
                        {item.content_type.replace('_', ' ')}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            statusColors[item.status] || ''
                          }`}
                        >
                          {item.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-dark-muted">v{item.current_version_number}</td>
                      <td className="py-3.5 px-4 text-dark-muted">{item.created_by}</td>
                      <td className="py-3.5 px-4 text-dark-muted">{item.reviewer_id || '—'}</td>
                      <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={(e) => handleDelete(e, item.id, item.title)}
                          className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Delete content item"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
