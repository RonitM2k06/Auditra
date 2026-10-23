import React from 'react';
import {
  LayoutDashboard,
  FileCheck2,
  FileEdit,
  BookOpen,
  CheckCircle2,
  History,
  BarChart3,
  Settings,
  ShieldCheck,
  ChevronDown,
  Building2,
  UserCheck,
  RotateCcw
} from 'lucide-react';
import { Brand } from '../types';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  brands: Brand[];
  selectedBrand: Brand | null;
  onSelectBrand: (brand: Brand) => void;
  userRole: 'creator' | 'reviewer' | 'admin';
  setUserRole: (role: 'creator' | 'reviewer' | 'admin') => void;
  pendingApprovalCount: number;
  onResetSample: () => void;
  onOpenNewBrandModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  setCurrentTab,
  brands,
  selectedBrand,
  onSelectBrand,
  userRole,
  setUserRole,
  pendingApprovalCount,
  onResetSample,
  onOpenNewBrandModal,
}) => {
  const [brandDropdownOpen, setBrandDropdownOpen] = React.useState(false);
  const [roleDropdownOpen, setRoleDropdownOpen] = React.useState(false);

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'reviews', label: 'Content Reviews', icon: FileCheck2 },
    { id: 'studio', label: 'Review Studio', icon: FileEdit, badge: 'Live' },
    { id: 'rulebook', label: 'Brand Rulebook', icon: BookOpen },
    {
      id: 'approvals',
      label: 'Approval Queue',
      icon: CheckCircle2,
      count: pendingApprovalCount,
    },
    { id: 'audit', label: 'Audit Trail', icon: History },
    { id: 'insights', label: 'Governance Insights', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const roleLabels = {
    creator: { title: 'Alex Rivers', subtitle: 'Content Creator' },
    reviewer: { title: 'Sarah Chen', subtitle: 'Brand Compliance Lead' },
    admin: { title: 'System Admin', subtitle: 'Governance Admin' },
  };

  return (
    <aside className="w-64 bg-navy-900 text-slate-300 flex flex-col h-screen border-r border-navy-800 select-none z-20 shrink-0">
      {/* Brand Header */}
      <div className="p-5 border-b border-navy-800/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-lg shadow-brand-500/20 text-white font-bold text-lg">
            <ShieldCheck className="w-5 h-5 text-navy-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold tracking-tight text-white font-sans">AUDITRA</span>
              <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-brand-500/20 text-brand-300 rounded border border-brand-500/30">
                v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Brand Governance Engine</p>
          </div>
        </div>

        {/* Workspace Switcher */}
        <div className="relative mt-4">
          <button
            onClick={() => setBrandDropdownOpen(!brandDropdownOpen)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs bg-navy-850 hover:bg-navy-800 rounded-lg border border-navy-700/60 text-slate-200 transition-colors"
          >
            <div className="flex items-center gap-2 truncate">
              <Building2 className="w-3.5 h-3.5 text-brand-400 shrink-0" />
              <span className="truncate font-medium">{selectedBrand?.name || 'Select Workspace'}</span>
              {selectedBrand?.is_sample && (
                <span className="text-[9px] bg-brand-500/20 text-brand-300 px-1 py-0.2 rounded font-mono">
                  DEMO
                </span>
              )}
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          </button>

          {brandDropdownOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-navy-850 border border-navy-700 rounded-lg shadow-2xl py-1 z-50 text-xs">
              <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Workspaces
              </div>
              {brands.map((b) => (
                <button
                  key={b.id}
                  onClick={() => {
                    onSelectBrand(b);
                    setBrandDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 flex items-center justify-between hover:bg-navy-800 transition-colors ${
                    selectedBrand?.id === b.id ? 'text-brand-400 font-semibold bg-navy-800/40' : 'text-slate-300'
                  }`}
                >
                  <span className="truncate">{b.name}</span>
                  {b.is_sample && <span className="text-[9px] text-slate-400">Sample</span>}
                </button>
              ))}
              <div className="border-t border-navy-700/60 mt-1 pt-1">
                <button
                  onClick={() => {
                    setBrandDropdownOpen(false);
                    onOpenNewBrandModal();
                  }}
                  className="w-full text-left px-3 py-1.5 text-slate-300 hover:text-white hover:bg-navy-800 flex items-center gap-2"
                >
                  + Create Brand
                </button>
                <button
                  onClick={() => {
                    setBrandDropdownOpen(false);
                    onResetSample();
                  }}
                  className="w-full text-left px-3 py-1.5 text-slate-400 hover:text-brand-300 hover:bg-navy-800 flex items-center gap-2"
                >
                  <RotateCcw className="w-3 h-3 text-slate-400" />
                  Reset Northstar Demo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setCurrentTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-brand-500/15 text-brand-300 border border-brand-500/30 shadow-sm'
                  : 'text-slate-300 hover:bg-navy-850 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-brand-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded bg-brand-500 text-navy-950">
                    {item.badge}
                  </span>
                )}
                {item.count !== undefined && item.count > 0 && (
                  <span className="px-1.5 py-0.5 text-[11px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {item.count}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </nav>

      {/* Role / Persona Switcher for Hackathon Testing */}
      <div className="p-3 border-t border-navy-800/80 bg-navy-950/60">
        <div className="text-[10px] uppercase font-semibold text-slate-400 px-1 mb-1.5 flex items-center justify-between">
          <span>Active Persona</span>
          <span className="text-[9px] text-slate-400">Demo Role</span>
        </div>

        <div className="relative">
          <button
            onClick={() => setRoleDropdownOpen(!roleDropdownOpen)}
            className="w-full flex items-center justify-between p-2 bg-navy-850 hover:bg-navy-800 rounded-lg border border-navy-700 text-left transition-colors"
          >
            <div className="flex items-center gap-2.5 truncate">
              <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center font-bold text-xs text-white">
                <UserCheck className="w-3.5 h-3.5 text-brand-400" />
              </div>
              <div className="truncate">
                <div className="text-xs font-semibold text-slate-200 truncate leading-none mb-1">
                  {roleLabels[userRole].title}
                </div>
                <div className="text-[10px] text-slate-400 truncate leading-none">
                  {roleLabels[userRole].subtitle}
                </div>
              </div>
            </div>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {roleDropdownOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-navy-850 border border-navy-700 rounded-lg shadow-2xl py-1 z-50 text-xs">
              <button
                onClick={() => {
                  setUserRole('creator');
                  setRoleDropdownOpen(false);
                }}
                className={`w-full text-left px-3 py-2 hover:bg-navy-800 ${
                  userRole === 'creator' ? 'text-brand-400 font-semibold' : 'text-slate-300'
                }`}
              >
                <div className="font-medium">Alex Rivers (Creator)</div>
                <div className="text-[10px] text-slate-400">Draft, edit, and apply fixes</div>
              </button>
              <button
                onClick={() => {
                  setUserRole('reviewer');
                  setRoleDropdownOpen(false);
                }}
                className={`w-full text-left px-3 py-2 hover:bg-navy-800 ${
                  userRole === 'reviewer' ? 'text-brand-400 font-semibold' : 'text-slate-300'
                }`}
              >
                <div className="font-medium">Sarah Chen (Compliance Lead)</div>
                <div className="text-[10px] text-slate-400">Approve, reject, request changes</div>
              </button>
              <button
                onClick={() => {
                  setUserRole('admin');
                  setRoleDropdownOpen(false);
                }}
                className={`w-full text-left px-3 py-2 hover:bg-navy-800 ${
                  userRole === 'admin' ? 'text-brand-400 font-semibold' : 'text-slate-300'
                }`}
              >
                <div className="font-medium">Administrator</div>
                <div className="text-[10px] text-slate-400">Full system & rule controls</div>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
