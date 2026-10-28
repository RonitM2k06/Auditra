/** Round 3 API shapes: identity, governance, evidence, creatives and brand intelligence. */

export type WorkspaceRole = 'creator' | 'reviewer' | 'admin';

export interface Me {
  id: string;
  email: string;
  display_name: string;
  is_demo: boolean;
  memberships: Array<{ brand_id: string; brand_name: string; role: WorkspaceRole; role_label: string }>;
}

export interface Member {
  user_id: string;
  email: string;
  display_name: string;
  role: WorkspaceRole;
  role_label: string;
  is_demo: boolean;
}

export interface Policy {
  id: string;
  name: string;
  condition_type: 'severity_at_least' | 'claim_status' | 'finding_category';
  condition_value: string;
  description: string;
  required_role: 'reviewer' | 'admin' | null;
  min_approvals: number;
  require_evidence_confirmation: boolean;
  is_active: boolean;
}

export interface ApprovalRequirement {
  name: string;
  trigger: string | null;
  reasons: string[];
  required_role: string | null;
  min_approvals: number;
  require_evidence_confirmation: boolean;
  met: boolean;
  missing: string[];
}

export interface ApprovalStatus {
  version_number: number;
  reviewed: boolean;
  approvals: Array<{ reviewer_name: string; reviewer_user_id: string; role: string; evidence_confirmed: boolean; created_at: string }>;
  requirements: ApprovalRequirement[];
  satisfied: boolean;
  blocking: string[];
}

export interface Publication {
  id: string;
  version_number: number;
  channel: string;
  status: string;
  published_by: string;
  destination: string;
  created_at: string;
  duplicate?: boolean;
}

export interface SourceRef {
  document_id: string;
  name: string;
  source_identifier?: string | null;
  section?: string | null;
  page?: number | null;
  effective_date?: string | null;
  expiry_date?: string | null;
  review_date?: string | null;
}

export type ClaimStatus = 'supported' | 'unsupported' | 'contradicted' | 'stale' | 'needs_review';

export interface ClaimCheck {
  id?: string;
  claim_text: string;
  start_offset: number;
  end_offset: number;
  status: ClaimStatus;
  rationale: string;
  retrieval_score: number;
  coverage: number;
  passage_id: string | null;
  passage_text: string | null;
  source: SourceRef | null;
  details: Record<string, any>;
}

export interface OcrLine {
  text: string;
  confidence: number;
  box: [number, number, number, number];
  start: number;
  end: number;
}

export interface CreativeImage {
  version_number: number;
  width: number;
  height: number;
  mime_type: string;
  byte_size: number;
  sha256: string;
  url: string;
  ocr: { engine: string; status: string; lines: OcrLine[]; text: string };
  visual: {
    contrast?: Array<{ line: number; text: string; box: number[]; ratio: number; threshold: number; large_text: boolean; text_color: string; background_color: string; uncertain: boolean; passes: boolean }>;
    palette?: { brand_palette: string[]; colours: Array<{ hex: string; share: number; neutral: boolean; nearest_brand_color: string | null; delta_e: number | null; on_palette: boolean }>; off_palette_share: number; threshold_delta_e: number };
    logo?: { status: string; score?: number; box?: number[] | null; detail: string };
  };
}

export interface VisualIdentity {
  palette: string[];
  extra_colors: string[];
  logo: { width: number; height: number; url: string } | null;
}

export interface SourceDoc {
  id: string;
  name: string;
  source_identifier: string | null;
  file_format: string;
  effective_date: string | null;
  expiry_date: string | null;
  review_date: string | null;
  approval_status: 'approved' | 'pending' | 'retired';
  sha256: string;
  char_count: number;
  uploaded_by: string;
  created_at: string;
  passage_count: number;
}

export interface SourceDocDetail extends SourceDoc {
  passages: Array<{ id: string; ordinal: number; section: string | null; page: number | null; text: string }>;
}

export interface DnaDimension {
  key: string;
  label: string;
  status: 'configured' | 'thin' | 'missing';
  count: number;
  items: Array<{ rule_id?: string; label: string; detail?: string; severity?: string; source?: string | null; color?: string; expired?: boolean; source_id?: string }>;
  explanation: string;
  observed_findings?: number;
}

export interface Contradiction {
  kind: string;
  certainty: 'definite' | 'possible';
  rule_ids: string[];
  title: string;
  explanation: string;
}

export interface BrandDna {
  dimensions: DnaDimension[];
  contradictions: Contradiction[];
  summary: Record<string, number>;
  scoring_note: string;
  rules: Record<string, { name: string; category: string; pattern: string | null; severity: string }>;
}

export interface RuleChange {
  op: 'add' | 'update' | 'disable' | 'enable' | 'delete';
  rule_id?: string;
  rule?: Record<string, any>;
}

export interface SimFinding {
  rule_id: string | null;
  category: string;
  severity: string;
  matched_text: string;
  start_offset: number;
  explanation: string;
}

export interface SimulationItem {
  content_id: string;
  title: string;
  status: string;
  version_number: number;
  media_kind: string;
  findings_before: number;
  findings_after: number;
  gained: SimFinding[];
  lost: SimFinding[];
  severity_changed: Array<{ before: SimFinding; after: SimFinding }>;
  unchanged: number;
  policies_added: string[];
  policies_removed: string[];
  approval_at_risk: boolean;
}

export interface Simulation {
  items: SimulationItem[];
  affected_items: number;
  new_contradictions: Contradiction[];
  note: string;
}

export interface Campaign {
  id: string;
  name: string;
  brief: string | null;
  created_by: string;
  created_at: string;
  assets: Array<{ content_id: string; title: string; content_type: string; status: string; media_kind: string; version_number: number }>;
}

export interface FactGroup {
  id: string;
  type: string;
  label: string;
  status: 'consistent' | 'confirmed_mismatch' | 'uncertain';
  context_similarity: number;
  explanation: string;
  members: Array<{ asset_id: string; display: string; value: string; passage: string; start: number; end: number }>;
}

export interface CampaignIssue {
  kind: 'confirmed_mismatch' | 'uncertain' | 'missing_information' | 'rule_conflict';
  title: string;
  explanation: string;
  asset_ids: string[];
  fact_id?: string;
  rule_id?: string;
  passage?: string;
  present_in?: string[];
  source_reference?: string;
}

export interface Consistency extends Campaign {
  facts: FactGroup[];
  issues: CampaignIssue[];
  counts: Record<string, number>;
  asset_texts: Record<string, string>;
  notice?: string;
}

export interface ReplayFinding {
  id: string;
  rule_id: string | null;
  category: string;
  severity: string;
  matched_text: string;
  explanation: string;
  source_reference: string | null;
  is_applied: boolean;
  is_dismissed: boolean;
}

export interface Replay {
  content_id: string;
  title: string;
  media_kind: string;
  versions: Array<{ version_number: number; created_by: string; change_summary: string | null; created_at: string; reviewed: boolean }>;
  from_version: number;
  to_version: number;
  diff: Array<{ op: 'equal' | 'insert' | 'delete'; text: string }>;
  findings: { persisted: ReplayFinding[]; changed: Array<{ before: ReplayFinding; after: ReplayFinding }>; new: ReplayFinding[]; resolved: ReplayFinding[] };
  review_runs: { from: string | null; to: string | null };
  rulebook: { from_snapshot: boolean; to_snapshot: boolean; diff: null | { added: any[]; removed: any[]; changed: Array<{ before: any; after: any; fields: string[] }> }; note: string | null };
  decisions: Array<{ decision: string; reviewer: string; role: string; version_number: number; evidence_confirmed: boolean; comments: string | null; created_at: string }>;
  timeline: Array<{ event_type: string; actor_name: string; actor_role: string; description: string; version: number | null; created_at: string }>;
  publications: Array<{ version_number: number; channel: string; created_at: string }>;
  integrity_note: string;
}
