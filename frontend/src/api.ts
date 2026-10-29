import {
  Brand, BrandRule, ApprovedClaim, ContentItem, ContentItemDetail,
  ReviewRun, Finding, DashboardStats, GovernanceInsights, AuditEvent,
  Me, Member, Policy, Publication, VisualIdentity, SourceDoc, SourceDocDetail, ClaimCheck,
  BrandDna, RuleChange, Simulation, SimulationItem, Campaign, Consistency, Replay, Comment
} from './types';
import type { RiskReport } from './components/RiskRadar';
import type { CopilotAnswer } from './components/Copilot';
import type { Proposal } from './components/Proposals';
import type { CoverageData } from './pages/Coverage';
import type { RemediationPreview, Suggestion } from './components/RemediationPanel';

const API_BASE = '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Auditra-Client': 'web',
      ...options?.headers,
    },
  });
  return handle<T>(res, endpoint);
}

/** Multipart upload (the browser sets the boundary, so no Content-Type header here). */
async function upload<T>(endpoint: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    body: form,
    credentials: 'same-origin',
    headers: { 'X-Auditra-Client': 'web' },
  });
  return handle<T>(res, endpoint);
}

async function handle<T>(res: Response, endpoint: string): Promise<T> {
  if (res.status === 401 && !endpoint.startsWith('/auth/')) {
    window.dispatchEvent(new Event('auditra:unauthorized'));
  }
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        // FastAPI validation errors arrive as a list; show their messages, not raw JSON.
        errorDetail = typeof errJson.detail === 'string'
          ? errJson.detail
          : Array.isArray(errJson.detail)
            ? errJson.detail.map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.slice(-1)[0] ?? 'request'}: ${d.msg ?? 'invalid'}`).join('; ')
            : JSON.stringify(errJson.detail);
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export interface ImpactClaim {
  claim_check_id: string;
  review_run_id: string;
  claim_text: string;
  status: string;
  passage_text: string | null;
  content_id: string;
  title: string;
  version_number: number;
  relation: 'confirmed' | 'historical' | 'possible' | 'missing_source';
  basis: string;
  checked_at: string | null;
}

export interface SourceImpactEntry {
  id: string;
  name: string;
  approval_status: string;
  effective_date: string | null;
  expiry_date: string | null;
  review_date: string | null;
  freshness: { status: string; date: string | null; reason: string };
  affects: boolean;
  claims: ImpactClaim[];
  possible: ImpactClaim[];
  assets: Array<{ content_id: string; title: string; status: string; version_number: number; claims: number; approved: boolean }>;
  campaigns: Array<{ id: string; name: string; content_ids: string[]; basis: string }>;
  notes: string[];
}

export interface SourceImpactData {
  today: string;
  sources: SourceImpactEntry[];
  missing_sources: ImpactClaim[];
  method: string;
}

export interface ReverifyResult {
  content_id: string;
  title: string;
  outcome: 'ok' | 'failed';
  before: string[];
  after?: string[];
  version_number?: number;
  approval_satisfied?: boolean;
  error?: string;
}

export interface TourStatus {
  ready: boolean;
  campaign: { id: string; name: string; brief: string | null; asset_count: number } | null;
  asset: { id: string; title: string; status: string; version: number; kind: 'seeded' | 'tour_copy' } | null;
  problem: 'missing_campaign' | 'missing_asset' | 'asset_used' | null;
  message: string | null;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  ai_engine: 'configured' | 'deterministic_fallback';
  database: string;
  commit?: string;
}

export const api = {
  health: () => request<HealthStatus>('/health'),

  // Brands
  getBrands: () => request<Brand[]>('/brands'),
  createBrand: (data: Partial<Brand>) => request<Brand>('/brands', { method: 'POST', body: JSON.stringify(data) }),
  updateBrand: (brandId: string, data: Partial<Brand>) =>
    request<Brand>(`/brands/${brandId}`, { method: 'PUT', body: JSON.stringify(data) }),
  resetSampleBrand: () => request<Brand>('/brands/sample/reset', { method: 'POST' }),

  // Rules & Claims
  getRules: (brandId: string, category?: string) =>
    request<BrandRule[]>(`/brands/${brandId}/rules${category ? `?category=${category}` : ''}`),
  createRule: (brandId: string, data: Partial<BrandRule>) =>
    request<BrandRule>(`/brands/${brandId}/rules`, { method: 'POST', body: JSON.stringify(data) }),
  updateRule: (brandId: string, ruleId: string, data: Partial<BrandRule>) =>
    request<BrandRule>(`/brands/${brandId}/rules/${ruleId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteRule: (brandId: string, ruleId: string) =>
    request<void>(`/brands/${brandId}/rules/${ruleId}`, { method: 'DELETE' }),

  getClaims: (brandId: string) => request<ApprovedClaim[]>(`/brands/${brandId}/claims`),
  createClaim: (brandId: string, data: Partial<ApprovedClaim>) =>
    request<ApprovedClaim>(`/brands/${brandId}/claims`, { method: 'POST', body: JSON.stringify(data) }),
  deleteClaim: (brandId: string, claimId: string) =>
    request<void>(`/brands/${brandId}/claims/${claimId}`, { method: 'DELETE' }),

  uploadGuidelines: (brandId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return upload<{ filename: string; rules_extracted: number; message: string }>(`/brands/${brandId}/rules/upload-guidelines`, formData);
  },

  // Content Items
  getContentItems: (brandId: string, status?: string) =>
    request<ContentItem[]>(`/brands/${brandId}/content${status ? `?status=${status}` : ''}`),
  getContentItem: (contentId: string) =>
    request<ContentItemDetail>(`/content/${contentId}`),
  createContentItem: (brandId: string, data: { title: string; content_type: string; body: string; created_by?: string }) =>
    request<ContentItemDetail>(`/brands/${brandId}/content`, { method: 'POST', body: JSON.stringify(data) }),
  updateContentItem: (contentId: string, data: { title?: string; content_type?: string; body?: string; change_summary?: string; actor_name?: string; actor_role?: string }) =>
    request<ContentItemDetail>(`/content/${contentId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteContentItem: (contentId: string) =>
    request<void>(`/content/${contentId}`, { method: 'DELETE' }),

  // Reviews & Findings
  runReview: (contentId: string, data?: { actor_name?: string; actor_role?: string; force_engine?: string }) =>
    request<ReviewRun>(`/content/${contentId}/review`, { method: 'POST', body: JSON.stringify(data || {}) }),
  applyCorrection: (findingId: string, data: { custom_replacement?: string; occurrence_offset?: number; actor_name?: string; actor_role?: string }) =>
    request<ContentItemDetail>(`/findings/${findingId}/apply`, { method: 'POST', body: JSON.stringify(data) }),
  dismissFinding: (findingId: string, actor_name?: string) =>
    request<Finding>(`/findings/${findingId}/dismiss?actor_name=${encodeURIComponent(actor_name || 'Reviewer')}`, { method: 'POST' }),

  // Workflow & Decisions
  submitForReview: (contentId: string, actor_name?: string, actor_role?: string) =>
    request<ContentItemDetail>(`/content/${contentId}/submit?actor_name=${encodeURIComponent(actor_name || 'Creator')}&actor_role=${encodeURIComponent(actor_role || 'Creator')}`, { method: 'POST' }),
  recordDecision: (contentId: string, data: { decision: string; reviewer_name?: string; reviewer_role?: string; comments?: string; version_number?: number; evidence_confirmed?: boolean }) =>
    request<ContentItemDetail>(`/content/${contentId}/decision`, { method: 'POST', body: JSON.stringify(data) }),
  addComment: (contentId: string, data: { text: string; author_name: string; author_role: string }) =>
    request<Comment>(`/content/${contentId}/comments`, { method: 'POST', body: JSON.stringify(data) }),

  // Audit, Dashboard & Insights
  getAuditTrail: (brandId: string, contentId?: string) =>
    request<AuditEvent[]>(`/brands/${brandId}/audit${contentId ? `?content_id=${contentId}` : ''}`),
  getDashboard: (brandId: string) =>
    request<DashboardStats>(`/brands/${brandId}/dashboard`),
  getInsights: (brandId: string) =>
    request<GovernanceInsights>(`/brands/${brandId}/insights`),

  // Authentication & members
  authConfig: () => request<{ demo_login: boolean; demo_personas: string[] }>('/auth/config'),
  me: () => request<Me>('/auth/me'),
  login: (email: string, password: string) => request<Me>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, display_name: string) =>
    request<Me>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, display_name }) }),
  demoLogin: (persona: string) => request<Me>('/auth/demo', { method: 'POST', body: JSON.stringify({ persona }) }),
  logout: () => request<{ signed_out: boolean }>('/auth/logout', { method: 'POST' }),
  getMembers: (brandId: string) => request<Member[]>(`/brands/${brandId}/members`),
  addMember: (brandId: string, email: string, role: string) =>
    request<Member[]>(`/brands/${brandId}/members`, { method: 'POST', body: JSON.stringify({ email, role }) }),
  updateMember: (brandId: string, userId: string, role: string) =>
    request<Member[]>(`/brands/${brandId}/members/${userId}`, { method: 'PUT', body: JSON.stringify({ role }) }),
  removeMember: (brandId: string, userId: string) => request<Member[]>(`/brands/${brandId}/members/${userId}`, { method: 'DELETE' }),

  // Policies & publishing
  getPolicies: (brandId: string) => request<Policy[]>(`/brands/${brandId}/policies`),
  createPolicy: (brandId: string, data: Partial<Policy>) => request<Policy>(`/brands/${brandId}/policies`, { method: 'POST', body: JSON.stringify(data) }),
  updatePolicy: (brandId: string, id: string, data: Partial<Policy>) =>
    request<Policy>(`/brands/${brandId}/policies/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePolicy: (brandId: string, id: string) => request<void>(`/brands/${brandId}/policies/${id}`, { method: 'DELETE' }),
  publish: (contentId: string, version_number: number) =>
    request<Publication>(`/content/${contentId}/publish`, { method: 'POST', body: JSON.stringify({ version_number, channel: 'sandbox' }) }),
  exportUrl: (publicationId: string) => `${API_BASE}/publications/${publicationId}/export`,

  // Creatives & visual identity
  uploadCreative: (brandId: string, title: string, contentType: string, file: File) => {
    const f = new FormData();
    f.append('title', title);
    f.append('content_type', contentType);
    f.append('file', file);
    return upload<ContentItemDetail>(`/brands/${brandId}/creatives`, f);
  },
  uploadRevisedCreative: (contentId: string, file: File) => {
    const f = new FormData();
    f.append('file', file);
    return upload<ContentItemDetail>(`/content/${contentId}/creative`, f);
  },
  getVisualIdentity: (brandId: string) => request<VisualIdentity>(`/brands/${brandId}/visual-identity`),
  setPalette: (brandId: string, colors: string[]) =>
    request<VisualIdentity>(`/brands/${brandId}/palette`, { method: 'PUT', body: JSON.stringify({ colors }) }),
  uploadLogo: (brandId: string, file: File) => {
    const f = new FormData();
    f.append('file', file);
    return upload<VisualIdentity>(`/brands/${brandId}/logo`, f);
  },

  // Evidence sources
  getSources: (brandId: string) => request<SourceDoc[]>(`/brands/${brandId}/sources`),
  getSource: (brandId: string, id: string) => request<SourceDocDetail>(`/brands/${brandId}/sources/${id}`),
  uploadSource: (brandId: string, file: File, meta: Record<string, string>) => {
    const f = new FormData();
    f.append('file', file);
    Object.entries(meta).forEach(([k, v]) => v && f.append(k, v));
    return upload<SourceDoc>(`/brands/${brandId}/sources`, f);
  },
  updateSource: (brandId: string, id: string, data: Partial<SourceDoc>) =>
    request<SourceDoc>(`/brands/${brandId}/sources/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSource: (brandId: string, id: string) => request<void>(`/brands/${brandId}/sources/${id}`, { method: 'DELETE' }),
  verifyText: (brandId: string, text: string) =>
    request<ClaimCheck[]>(`/brands/${brandId}/evidence/verify`, { method: 'POST', body: JSON.stringify({ text }) }),

  // Intelligence
  getDna: (brandId: string) => request<BrandDna>(`/brands/${brandId}/dna`),
  simulate: (brandId: string, changes: RuleChange[]) =>
    request<Simulation>(`/brands/${brandId}/simulate`, { method: 'POST', body: JSON.stringify({ changes }) }),
  getCampaigns: (brandId: string) => request<Campaign[]>(`/brands/${brandId}/campaigns`),
  createCampaign: (brandId: string, data: { name: string; brief?: string; content_ids: string[] }) =>
    request<Campaign>(`/brands/${brandId}/campaigns`, { method: 'POST', body: JSON.stringify(data) }),
  updateCampaign: (id: string, data: { name: string; brief?: string; content_ids: string[] }) =>
    request<Campaign>(`/campaigns/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCampaign: (id: string) => request<void>(`/campaigns/${id}`, { method: 'DELETE' }),
  getConsistency: (id: string) => request<Consistency>(`/campaigns/${id}/consistency`),
  getCampaignRisk: (id: string) => request<RiskReport>(`/campaigns/${id}/risk`),
  getProposals: (brandId: string) => request<Proposal[]>(`/brands/${brandId}/rule-proposals`),
  createProposal: (brandId: string, title: string, rationale: string, changes: RuleChange[]) =>
    request<Proposal>(`/brands/${brandId}/rule-proposals`, { method: 'POST', body: JSON.stringify({ title, rationale, changes }) }),
  rerunProposal: (id: string) => request<Proposal>(`/rule-proposals/${id}/rerun`, { method: 'POST' }),
  decideProposal: (id: string, decision: 'activate' | 'reject', confirm: boolean, note: string) =>
    request<Proposal>(`/rule-proposals/${id}/decision`, { method: 'POST', body: JSON.stringify({ decision, confirm, note }) }),
  getCoverage: (brandId: string) => request<CoverageData>(`/brands/${brandId}/coverage`),
  askCopilot: (brandId: string, question: string, history: Array<{ role: string; content: string }>) =>
    request<CopilotAnswer>(`/brands/${brandId}/copilot`, { method: 'POST', body: JSON.stringify({ question, history }) }),
  getRemediation: (contentId: string) =>
    request<{ analysed: boolean; suggestions: Suggestion[]; notice: string | null }>(`/content/${contentId}/remediation`),
  previewRemediation: (contentId: string, version_number: number, fixes: Array<{ id: string; replacement?: string }>) =>
    request<RemediationPreview>(`/content/${contentId}/remediation/preview`, { method: 'POST', body: JSON.stringify({ version_number, fixes }) }),
  applyRemediation: (contentId: string, version_number: number, fixes: Array<{ id: string; replacement?: string }>, confirm_factual: boolean) =>
    request<ContentItemDetail>(`/content/${contentId}/remediation/apply`, { method: 'POST', body: JSON.stringify({ version_number, fixes, confirm_factual }) }),
  getReplay: (contentId: string, from?: number, to?: number) =>
    request<Replay>(`/content/${contentId}/replay?${from ? `from_version=${from}&` : ''}${to ? `to_version=${to}` : ''}`),
  counterfactual: (contentId: string, version: number, changes: RuleChange[]) =>
    request<SimulationItem & { note: string }>(`/content/${contentId}/versions/${version}/counterfactual`, { method: 'POST', body: JSON.stringify({ changes }) }),

  // Source-expiry impact
  getSourceImpact: (brandId: string) => request<SourceImpactData>(`/brands/${brandId}/source-impact`),
  reverifySource: (brandId: string, sourceId: string, content_ids?: string[]) =>
    request<{ results: ReverifyResult[]; note: string }>(`/brands/${brandId}/sources/${sourceId}/reverify`, { method: 'POST', body: JSON.stringify(content_ids ? { content_ids } : {}) }),

  // Guided tour (fixture lookup and labelled copy only; the tour drives the normal endpoints)
  getTourStatus: (brandId: string) => request<TourStatus>(`/brands/${brandId}/tour`),
  createTourCopy: (brandId: string) => request<TourStatus>(`/brands/${brandId}/tour/copy`, { method: 'POST' }),
};
