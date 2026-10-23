import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
  Clock,
  HelpCircle,
  ShieldCheck
} from 'lucide-react';
import { GovernanceInsights as InsightsType, Brand } from '../types';
import { api } from '../api';

interface GovernanceInsightsProps {
  brand: Brand;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const GovernanceInsights: React.FC<GovernanceInsightsProps> = ({ brand, showToast }) => {
  const [insights, setInsights] = useState<InsightsType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInsights();
  }, [brand.id]);

  const loadInsights = async () => {
    setLoading(true);
    try {
      const data = await api.getInsights(brand.id);
      setInsights(data);
    } catch (err: any) {
      showToast(err.message || 'Failed to load governance insights', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (loading || !insights) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center text-xs text-dark-muted">
        Loading governance insights and violation analytics...
      </div>
    );
  }

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-surface-base">
      <div>
        <h2 className="text-xl font-bold text-dark-primary">Governance Insights & Analytics</h2>
        <p className="text-xs text-dark-muted mt-0.5">
          Empirical patterns across scans, recurring editorial friction, and rule clarity optimizations.
        </p>
      </div>

      {/* Top Turnaround & Quality Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-surface-border p-4 shadow-xs">
          <div className="text-xs font-semibold text-dark-muted mb-1">Total Compliance Decisions</div>
          <div className="text-2xl font-bold text-dark-primary font-mono">
            {insights.approval_turnaround_summary.total_governance_decisions}
          </div>
          <div className="text-[11px] text-dark-muted mt-1">Recorded human evaluations</div>
        </div>

        <div className="bg-white rounded-xl border border-surface-border p-4 shadow-xs">
          <div className="text-xs font-semibold text-dark-muted mb-1">First-Pass Approval Rate</div>
          <div className="text-2xl font-bold text-emerald-600 font-mono">
            {insights.approval_turnaround_summary.first_pass_approval_rate}
          </div>
          <div className="text-[11px] text-dark-muted mt-1">Drafts approved without rework</div>
        </div>

        <div className="bg-white rounded-xl border border-surface-border p-4 shadow-xs">
          <div className="text-xs font-semibold text-dark-muted mb-1">Changes Requested Count</div>
          <div className="text-2xl font-bold text-amber-600 font-mono">
            {insights.approval_turnaround_summary.changes_requested_count}
          </div>
          <div className="text-[11px] text-dark-muted mt-1">Content sent back for revision</div>
        </div>

        <div className="bg-white rounded-xl border border-surface-border p-4 shadow-xs">
          <div className="text-xs font-semibold text-dark-muted mb-1">Average Review Turnaround</div>
          <div className="text-2xl font-bold text-blue-600 font-mono">
            {insights.approval_turnaround_summary.average_turnaround_hours}h
          </div>
          <div className="text-[11px] text-dark-muted mt-1">Submission to decision time</div>
        </div>
      </div>

      {/* Middle Row: Violation Categories & Most Triggered Rules */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Most Frequent Categories */}
        <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs">
          <h3 className="text-sm font-bold text-dark-primary mb-1">Most Frequent Violation Categories</h3>
          <p className="text-xs text-dark-muted mb-4">Relative distribution across all analyzed draft versions</p>

          <div className="space-y-3.5">
            {insights.most_frequent_categories.map((cat) => (
              <div key={cat.category} className="text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-dark-secondary capitalize">
                    {cat.category.replace('_', ' ')}
                  </span>
                  <span className="font-mono text-dark-muted">
                    {cat.count} flags ({cat.percentage}%)
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all"
                    style={{ width: `${cat.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Most Triggered Rules */}
        <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs">
          <h3 className="text-sm font-bold text-dark-primary mb-1">Highest Friction Rules</h3>
          <p className="text-xs text-dark-muted mb-4">Specific brand rules most commonly triggered by creators</p>

          <div className="space-y-3">
            {insights.most_triggered_rules.map((rule) => (
              <div
                key={rule.rule_id}
                className="p-3 bg-surface-base rounded-lg border border-surface-border flex items-center justify-between text-xs"
              >
                <div>
                  <div className="font-semibold text-dark-primary">{rule.rule_name}</div>
                  <div className="text-[10px] text-dark-muted uppercase font-bold tracking-wider mt-0.5">
                    {rule.category.replace('_', ' ')} • {rule.severity}
                  </div>
                </div>
                <div className="text-right">
                  <span className="px-2 py-1 rounded bg-red-50 text-red-700 font-mono font-bold">
                    {rule.trigger_count}x
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Rule Clarity & Governance Recommendations */}
      <div className="bg-white rounded-xl border border-surface-border p-6 shadow-xs">
        <div className="flex items-center gap-2 mb-1">
          <Lightbulb className="w-4 h-4 text-amber-500" />
          <h3 className="text-sm font-bold text-dark-primary">Rule Clarity & Governance Recommendations</h3>
        </div>
        <p className="text-xs text-dark-muted mb-4">
          Hypotheses generated from empirical violation clusters to streamline brand policy adoption.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights.rule_clarity_insights.map((item, idx) => (
            <div
              key={idx}
              className="p-4 bg-amber-50/50 border border-amber-200/80 rounded-xl space-y-2 text-xs"
            >
              <div className="font-bold text-dark-primary text-sm flex items-center justify-between">
                <span>{item.title}</span>
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.2 bg-amber-100 text-amber-800 rounded">
                  {item.type.replace('_', ' ')}
                </span>
              </div>
              <p className="text-dark-secondary leading-relaxed">
                <span className="font-semibold">Hypothesis: </span>
                {item.hypothesis}
              </p>
              <div className="p-2.5 bg-white/80 rounded-lg border border-amber-200 text-dark-primary font-medium">
                <span className="font-bold text-emerald-800">Recommendation: </span>
                {item.recommendation}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
