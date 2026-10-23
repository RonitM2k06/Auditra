import React, { useEffect, useState } from 'react';
import {
  FileCheck2,
  Clock,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  BookOpen
} from 'lucide-react';
import { DashboardStats, Brand } from '../types';
import { api } from '../api';

interface OverviewDashboardProps {
  brand: Brand;
  onOpenContent: (contentId: string) => void;
  onNavigateTab: (tab: string) => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  brand,
  onOpenContent,
  onNavigateTab,
  showToast,
}) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, [brand.id]);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const data = await api.getDashboard(brand.id);
      setStats(data);
    } catch (err: any) {
      showToast(err.message || 'Failed to load dashboard metrics', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (loading || !stats) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center">
        <div className="text-xs text-dark-muted font-medium flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          Loading Command Centre metrics...
        </div>
      </div>
    );
  }

  const kpis = [
    {
      title: 'Total Governed Assets',
      value: stats.total_reviews,
      subtitle: 'Managed across all channels',
      icon: FileCheck2,
      color: 'text-brand-600 bg-brand-50 border-brand-200',
    },
    {
      title: 'Awaiting Compliance Approval',
      value: stats.awaiting_approval,
      subtitle: 'In human reviewer queue',
      icon: Clock,
      color: 'text-blue-600 bg-blue-50 border-blue-200',
    },
    {
      title: 'High / Critical Risk Assets',
      value: stats.high_severity_issues,
      subtitle: 'Require mandatory correction',
      icon: AlertTriangle,
      color: 'text-amber-600 bg-amber-50 border-amber-200',
    },
    {
      title: 'Approved for Publication',
      value: stats.approved_reviews,
      subtitle: 'Certified brand compliant',
      icon: CheckCircle2,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
    },
  ];

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-8 bg-surface-base">
      {/* Top Banner / Welcome */}
      <div className="bg-gradient-to-r from-navy-900 to-navy-850 rounded-2xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border border-navy-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-brand-500/20 text-brand-300 border border-brand-500/30">
              Active Brand Workspace
            </span>
            <span className="text-xs text-slate-400 font-mono">{brand.industry}</span>
          </div>
          <h2 className="text-xl font-bold tracking-tight">{brand.name} Command Centre</h2>
          <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
            {brand.description ||
              'Real-time brand compliance monitoring, deterministic rule evaluation, and human governance approval tracking.'}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => onNavigateTab('studio')}
            className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold shadow-md transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Launch Review Studio</span>
          </button>
          <button
            onClick={() => onNavigateTab('rulebook')}
            className="flex items-center gap-1.5 px-4 py-2 bg-navy-800 hover:bg-navy-750 text-slate-200 rounded-lg text-xs font-semibold border border-navy-700 transition-all"
          >
            <BookOpen className="w-3.5 h-3.5 text-brand-400" />
            <span>View Rulebook</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div
              key={idx}
              className="bg-white rounded-xl border border-surface-border p-5 shadow-xs flex flex-col justify-between"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-dark-muted">{kpi.title}</span>
                <div className={`w-8 h-8 rounded-lg border flex items-center justify-center ${kpi.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <div>
                <div className="text-3xl font-extrabold text-dark-primary font-mono tracking-tight">
                  {kpi.value}
                </div>
                <div className="text-[11px] text-dark-muted mt-1">{kpi.subtitle}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Middle Row: Status Distribution & Severity Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Breakdown Card */}
        <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-dark-primary mb-1">Workflow Status Distribution</h3>
            <p className="text-xs text-dark-muted mb-4">Lifecycle status of all registered content assets</p>

            <div className="space-y-3 text-xs">
              {Object.entries(stats.status_counts).map(([st, count]) => {
                const total = stats.total_reviews || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={st}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="capitalize font-medium text-dark-secondary">{st.replace('_', ' ')}</span>
                      <span className="font-mono text-dark-muted">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          st === 'approved'
                            ? 'bg-emerald-500'
                            : st === 'in_review'
                            ? 'bg-blue-500'
                            : st === 'changes_requested'
                            ? 'bg-amber-500'
                            : st === 'rejected'
                            ? 'bg-red-500'
                            : 'bg-slate-400'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Severity Risk Distribution */}
        <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-dark-primary mb-1">Active Severity Distribution</h3>
            <p className="text-xs text-dark-muted mb-4">Unresolved policy violations in current revisions</p>

            <div className="grid grid-cols-2 gap-3 text-center mb-4">
              <div className="p-3 bg-red-50/70 border border-red-200 rounded-lg">
                <div className="text-2xl font-bold text-red-600 font-mono">
                  {stats.severity_distribution.critical || 0}
                </div>
                <div className="text-xs font-semibold text-red-700 uppercase mt-0.5">Critical</div>
              </div>
              <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg">
                <div className="text-2xl font-bold text-amber-600 font-mono">
                  {stats.severity_distribution.high || 0}
                </div>
                <div className="text-xs font-semibold text-amber-700 uppercase mt-0.5">High</div>
              </div>
              <div className="p-3 bg-blue-50/70 border border-blue-200 rounded-lg">
                <div className="text-2xl font-bold text-blue-600 font-mono">
                  {stats.severity_distribution.medium || 0}
                </div>
                <div className="text-xs font-semibold text-blue-700 uppercase mt-0.5">Medium</div>
              </div>
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <div className="text-2xl font-bold text-slate-600 font-mono">
                  {stats.severity_distribution.low || 0}
                </div>
                <div className="text-xs font-semibold text-slate-600 uppercase mt-0.5">Low</div>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-dark-muted bg-surface-muted p-2 rounded flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-500 shrink-0" />
            <span>Deterministic engine ensures zero halluncinated policy citations.</span>
          </div>
        </div>

        {/* Recent Activity Mini-Feed */}
        <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-bold text-dark-primary">Recent Governance Events</h3>
              <button
                onClick={() => onNavigateTab('audit')}
                className="text-xs text-brand-600 hover:text-brand-700 font-medium"
              >
                View all
              </button>
            </div>
            <p className="text-xs text-dark-muted mb-4">Immutable audit events recorded</p>

            <div className="space-y-3 overflow-y-auto max-h-56 pr-1">
              {stats.recent_activity.slice(0, 5).map((ev) => (
                <div key={ev.id} className="text-xs flex items-start gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-brand-500 mt-1.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-dark-secondary font-medium truncate">{ev.description}</p>
                    <div className="text-[10px] text-dark-muted flex items-center gap-2 mt-0.5">
                      <span>{ev.actor_name}</span>
                      <span>•</span>
                      <span>{new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Table: Recent Content Submissions */}
      <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-dark-primary">Recent Content Reviews</h3>
            <p className="text-xs text-dark-muted">Open any piece of content to inspect findings or revise</p>
          </div>
          <button
            onClick={() => onNavigateTab('reviews')}
            className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-semibold"
          >
            <span>See all reviews</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-surface-border text-dark-muted uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Title</th>
                <th className="py-2.5 px-3">Channel</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Version</th>
                <th className="py-2.5 px-3">Author</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {stats.recent_reviews.map((rev) => {
                const statusClasses: Record<string, string> = {
                  draft: 'bg-slate-100 text-slate-700',
                  in_review: 'bg-blue-100 text-blue-800',
                  changes_requested: 'bg-amber-100 text-amber-800',
                  approved: 'bg-emerald-100 text-emerald-800',
                  rejected: 'bg-red-100 text-red-800',
                };
                return (
                  <tr key={rev.id} className="hover:bg-surface-muted/50 transition-colors">
                    <td className="py-3 px-3 font-semibold text-dark-primary">{rev.title}</td>
                    <td className="py-3 px-3 capitalize text-dark-muted">{rev.content_type.replace('_', ' ')}</td>
                    <td className="py-3 px-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusClasses[rev.status] || ''}`}>
                        {rev.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-dark-muted">v{rev.current_version_number}</td>
                    <td className="py-3 px-3 text-dark-muted">{rev.created_by}</td>
                    <td className="py-3 px-3 text-right">
                      <button
                        onClick={() => onOpenContent(rev.id)}
                        className="px-2.5 py-1 bg-surface-muted hover:bg-brand-50 hover:text-brand-700 text-dark-secondary rounded text-xs font-semibold transition-colors"
                      >
                        Open Studio
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
