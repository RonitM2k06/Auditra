import React, { useState, useEffect } from 'react';
import { History, Filter, User, Calendar, ShieldCheck, ArrowRight, Tag } from 'lucide-react';
import { AuditEvent, Brand } from '../types';
import { api } from '../api';

interface AuditTrailProps {
  brand: Brand;
  showToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const AuditTrail: React.FC<AuditTrailProps> = ({ brand, showToast }) => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState('all');

  useEffect(() => {
    loadEvents();
  }, [brand.id, eventFilter]);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditTrail(brand.id, undefined);
      setEvents(data);
    } catch (err: any) {
      showToast(err.message || 'Failed to load audit events', 'error');
    } finally {
      setLoading(false);
    }
  };

  const filteredEvents = events.filter((e) => {
    if (eventFilter === 'all') return true;
    return e.event_type === eventFilter;
  });

  const getEventBadge = (type: string) => {
    switch (type) {
      case 'content_approved':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'changes_requested':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'content_rejected':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'correction_applied':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'analysis_run':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-surface-base">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-dark-primary">Audit Trail & Governance Log</h2>
            <span className="text-xs px-2 py-0.5 rounded bg-surface-muted text-dark-muted font-mono font-semibold">
              Append-Only Ledger
            </span>
          </div>
          <p className="text-xs text-dark-muted mt-0.5">
            Traceable chronology of all draft modifications, compliance scans, applied corrections, and reviewer decisions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="text-xs bg-white border border-surface-border rounded-lg px-3 py-1.5 text-dark-secondary focus:outline-none"
          >
            <option value="all">All Events ({events.length})</option>
            <option value="content_approved">Approved Only</option>
            <option value="changes_requested">Changes Requested</option>
            <option value="correction_applied">Corrections Applied</option>
            <option value="analysis_run">Analysis Scans</option>
            <option value="draft_created">Drafts Created</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-dark-muted">Loading audit history...</div>
      ) : filteredEvents.length === 0 ? (
        <div className="p-12 text-center text-xs text-dark-muted bg-white rounded-xl border border-surface-border">
          No audit records found.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-surface-border shadow-xs p-6">
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
            {filteredEvents.map((ev) => (
              <div key={ev.id} className="relative group">
                {/* Timeline dot */}
                <div className="absolute -left-[19px] top-1.5 w-3 h-3 rounded-full bg-white border-2 border-brand-500 group-hover:scale-125 transition-transform" />

                <div className="bg-surface-base border border-surface-border rounded-xl p-4 hover:border-slate-300 transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getEventBadge(
                          ev.event_type
                        )}`}
                      >
                        {ev.event_type.replace('_', ' ')}
                      </span>
                      <span className="text-xs font-semibold text-dark-primary">{ev.actor_name}</span>
                      <span className="text-[11px] text-dark-muted">({ev.actor_role})</span>
                    </div>

                    <div className="text-[11px] text-dark-muted font-mono flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-400" />
                      <span>{new Date(ev.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  <p className="text-xs text-dark-secondary leading-relaxed">{ev.description}</p>

                  {ev.event_metadata && Object.keys(ev.event_metadata).length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-slate-200/60 flex items-center gap-2 overflow-x-auto text-[11px] text-dark-muted font-mono">
                      <span className="font-semibold text-slate-500 font-sans">Metadata:</span>
                      {Object.entries(ev.event_metadata).map(([k, v]) => (
                        <span key={k} className="px-1.5 py-0.2 bg-white rounded border border-slate-200">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
