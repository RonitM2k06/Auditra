export interface Brand {
  id: string;
  name: string;
  slug: string;
  industry: string;
  description?: string;
  is_sample: boolean;
  primary_color: string;
  secondary_color: string;
  created_at: string;
  updated_at: string;
}

export interface BrandRule {
  id: string;
  brand_id: string;
  name: string;
  category: 'tone_voice' | 'preferred_term' | 'prohibited_term' | 'required_phrase' | 'approved_claim' | 'restricted_claim' | 'formatting_style';
  description: string;
  rule_text: string;
  match_pattern?: string;
  suggested_replacement?: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  is_active: boolean;
  source_reference?: string;
  created_at: string;
  updated_at: string;
}

export interface ApprovedClaim {
  id: string;
  brand_id: string;
  claim_statement: string;
  topic: string;
  evidence_source: string;
  verification_date?: string;
  is_active: boolean;
  created_at: string;
}

export interface Finding {
  id: string;
  review_run_id: string;
  content_version_id: string;
  rule_id?: string;
  category: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  matched_text: string;
  start_offset: number;
  end_offset: number;
  explanation: string;
  source_reference?: string;
  suggested_correction?: string;
  confidence: number;
  requires_human_review: boolean;
  is_applied: boolean;
  is_dismissed: boolean;
  finding_source: string;
  region_json?: string | null;
  created_at: string;
}

export interface ReviewRun {
  id: string;
  content_id: string;
  content_version_id: string;
  brand_id: string;
  engine_type: 'deterministic' | 'hybrid_ai' | 'multimodal';
  ai_status: 'configured' | 'fallback_rule_based' | 'failed' | 'skipped';
  status: 'completed' | 'failed';
  risk_score: number;
  summary?: string;
  severity_counts: {
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
  };
  category_breakdown: Record<string, number>;
  created_at: string;
  findings: Finding[];
}

export interface ContentVersion {
  id: string;
  content_id: string;
  version_number: number;
  body: string;
  change_summary?: string;
  created_by: string;
  created_at: string;
}

export interface Comment {
  id: string;
  content_id: string;
  content_version_id?: string;
  author_name: string;
  author_role: string;
  text: string;
  created_at: string;
}

export interface ReviewDecision {
  id: string;
  content_id: string;
  content_version_id: string;
  decision: 'approved' | 'changes_requested' | 'rejected';
  reviewer_name: string;
  reviewer_role: string;
  reviewer_user_id?: string;
  evidence_confirmed?: boolean;
  comments?: string;
  created_at: string;
}

export interface ContentItem {
  id: string;
  brand_id: string;
  title: string;
  content_type: 'social_post' | 'advertisement' | 'email' | 'landing_page' | 'announcement' | 'blog_post';
  status: 'draft' | 'in_review' | 'changes_requested' | 'approved' | 'rejected';
  current_version_number: number;
  created_by: string;
  reviewer_id?: string;
  media_kind?: 'text' | 'image';
  approved_version_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentItemDetail extends ContentItem {
  versions: ContentVersion[];
  current_version?: ContentVersion;
  latest_review?: ReviewRun;
  comments: Comment[];
  decisions: ReviewDecision[];
  claim_checks: ClaimCheck[];
  approval_status?: ApprovalStatus;
  publications: Publication[];
  image?: CreativeImage | null;
}

export interface AuditEvent {
  id: string;
  brand_id: string;
  content_id?: string;
  event_type: string;
  actor_name: string;
  actor_role: string;
  description: string;
  event_metadata?: Record<string, any>;
  created_at: string;
}

export interface DashboardStats {
  total_reviews: number;
  awaiting_approval: number;
  high_severity_issues: number;
  approved_reviews: number;
  status_counts: Record<string, number>;
  severity_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  recent_reviews: ContentItem[];
  recent_activity: AuditEvent[];
}

export interface GovernanceInsights {
  most_frequent_categories: Array<{ category: string; count: number; percentage: number }>;
  most_triggered_rules: Array<{ rule_id: string; rule_name: string; category: string; severity: string; trigger_count: number }>;
  recurring_unresolved_issues: Array<{ id: string; matched_text: string; category: string; severity: string; explanation: string; suggested_correction?: string; created_at: string }>;
  approval_turnaround_summary: {
    total_governance_decisions: number;
    first_pass_approval_rate: string;
    changes_requested_count: number;
    average_turnaround_hours: number;
  };
  rule_clarity_insights: Array<{ title: string; type: string; hypothesis: string; recommendation: string }>;
}

export * from './types_r3';
import type { ClaimCheck, ApprovalStatus, Publication, CreativeImage } from './types_r3';
