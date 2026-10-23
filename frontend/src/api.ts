import {
  Brand, BrandRule, ApprovedClaim, ContentItem, ContentItemDetail,
  ReviewRun, Finding, DashboardStats, GovernanceInsights, AuditEvent
} from './types';

const API_BASE = '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch (_) {}
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

export const api = {
  // Brands
  getBrands: () => request<Brand[]>('/brands'),
  createBrand: (data: Partial<Brand>) => request<Brand>('/brands', { method: 'POST', body: JSON.stringify(data) }),
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

  uploadGuidelines: async (brandId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/brands/${brandId}/rules/upload-guidelines`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Guideline upload failed');
    }
    return res.json();
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
  applyCorrection: (findingId: string, data: { custom_replacement?: string; actor_name?: string; actor_role?: string }) =>
    request<ContentItemDetail>(`/findings/${findingId}/apply`, { method: 'POST', body: JSON.stringify(data) }),
  dismissFinding: (findingId: string, actor_name?: string) =>
    request<Finding>(`/findings/${findingId}/dismiss?actor_name=${encodeURIComponent(actor_name || 'Reviewer')}`, { method: 'POST' }),

  // Workflow & Decisions
  submitForReview: (contentId: string, actor_name?: string, actor_role?: string) =>
    request<ContentItemDetail>(`/content/${contentId}/submit?actor_name=${encodeURIComponent(actor_name || 'Creator')}&actor_role=${encodeURIComponent(actor_role || 'Creator')}`, { method: 'POST' }),
  recordDecision: (contentId: string, data: { decision: string; reviewer_name: string; reviewer_role: string; comments?: string }) =>
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
};
