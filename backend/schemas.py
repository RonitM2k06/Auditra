from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# --- Brands ---
class BrandBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    industry: str = Field("Technology", max_length=100)
    description: Optional[str] = None
    primary_color: str = Field("#0F9D91", max_length=20)
    secondary_color: str = Field("#101B2D", max_length=20)

class BrandCreate(BrandBase):
    slug: Optional[str] = None
    is_sample: bool = False

class BrandUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None

class BrandResponse(BrandBase):
    id: str
    slug: str
    is_sample: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

# --- Brand Rules ---
class BrandRuleBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    category: str = Field(..., description="tone_voice, preferred_term, prohibited_term, required_phrase, approved_claim, restricted_claim, formatting_style")
    description: str
    rule_text: str
    match_pattern: Optional[str] = None
    suggested_replacement: Optional[str] = None
    severity: str = Field("medium", description="critical, high, medium, low")
    is_active: bool = True
    source_reference: Optional[str] = None

class BrandRuleCreate(BrandRuleBase):
    pass

class BrandRuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    rule_text: Optional[str] = None
    match_pattern: Optional[str] = None
    suggested_replacement: Optional[str] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None
    source_reference: Optional[str] = None

class BrandRuleResponse(BrandRuleBase):
    id: str
    brand_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

# --- Approved Claims ---
class ApprovedClaimBase(BaseModel):
    claim_statement: str
    topic: str = "General"
    evidence_source: str
    verification_date: Optional[str] = None
    is_active: bool = True

class ApprovedClaimCreate(ApprovedClaimBase):
    pass

class ApprovedClaimResponse(ApprovedClaimBase):
    id: str
    brand_id: str
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Findings ---
class FindingResponse(BaseModel):
    id: str
    review_run_id: str
    content_version_id: str
    rule_id: Optional[str] = None
    category: str
    severity: str
    matched_text: str
    start_offset: int
    end_offset: int
    explanation: str
    source_reference: Optional[str] = None
    suggested_correction: Optional[str] = None
    confidence: float
    requires_human_review: bool
    is_applied: bool
    is_dismissed: bool
    finding_source: str
    region_json: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class FindingApplyRequest(BaseModel):
    custom_replacement: Optional[str] = None
    occurrence_offset: Optional[int] = Field(None, ge=0, description="Character offset of the occurrence to replace when the text appears more than once")
    actor_name: str = "Creator"
    actor_role: str = "Content Creator"

# --- Review Runs ---
class ReviewRunRequest(BaseModel):
    actor_name: str = "Creator"
    actor_role: str = "Content Creator"
    force_engine: Optional[str] = None  # deterministic or hybrid_ai

class ReviewRunResponse(BaseModel):
    id: str
    content_id: str
    content_version_id: str
    brand_id: str
    engine_type: str
    ai_status: str
    status: str
    risk_score: int
    summary: Optional[str] = None
    severity_counts: Dict[str, int]
    category_breakdown: Dict[str, int]
    created_at: datetime
    findings: List[FindingResponse] = []

    model_config = {"from_attributes": True}

# --- Content Versions ---
class ContentVersionResponse(BaseModel):
    id: str
    content_id: str
    version_number: int
    body: str
    change_summary: Optional[str] = None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Content Items ---
class ContentItemCreate(BaseModel):
    brand_id: Optional[str] = None  # taken from the URL path; accepted for backwards compatibility
    title: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field("social_post", max_length=60)
    body: str = Field(..., min_length=1, max_length=50000)
    created_by: str = "Creator"  # ignored: the author is the signed-in user

class ContentItemUpdate(BaseModel):
    title: Optional[str] = None
    content_type: Optional[str] = None
    body: Optional[str] = Field(None, max_length=50000)
    change_summary: Optional[str] = Field(None, max_length=255)
    actor_name: str = "Creator"
    actor_role: str = "Content Creator"

class ContentItemResponse(BaseModel):
    id: str
    brand_id: str
    title: str
    content_type: str
    status: str
    current_version_number: int
    created_by: str
    reviewer_id: Optional[str] = None
    media_kind: str = "text"
    approved_version_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    author_name: str = "Reviewer"
    author_role: str = "Brand Reviewer"

class CommentResponse(BaseModel):
    id: str
    content_id: str
    content_version_id: Optional[str] = None
    author_name: str
    author_role: str
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}

class ReviewDecisionCreate(BaseModel):
    decision: str = Field(..., description="approved, changes_requested, rejected")
    reviewer_name: str = "Reviewer"
    reviewer_role: str = "Brand Reviewer"
    comments: Optional[str] = Field(None, max_length=4000)
    version_number: Optional[int] = Field(None, ge=1, description="Version the reviewer inspected; required to approve")
    evidence_confirmed: bool = False

class ReviewDecisionResponse(BaseModel):
    id: str
    content_id: str
    content_version_id: str
    decision: str
    reviewer_name: str
    reviewer_role: str
    reviewer_user_id: Optional[str] = None
    evidence_confirmed: bool = False
    comments: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ContentItemDetailResponse(ContentItemResponse):
    versions: List[ContentVersionResponse] = []
    current_version: Optional[ContentVersionResponse] = None
    latest_review: Optional[ReviewRunResponse] = None
    comments: List[CommentResponse] = []
    decisions: List[ReviewDecisionResponse] = []
    claim_checks: List[Dict[str, Any]] = []
    approval_status: Optional[Dict[str, Any]] = None
    publications: List[Dict[str, Any]] = []
    image: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}

# --- Audit Events ---
class AuditEventResponse(BaseModel):
    id: str
    brand_id: str
    content_id: Optional[str] = None
    event_type: str
    actor_name: str
    actor_role: str
    description: str
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Dashboard & Insights ---
class DashboardStatsResponse(BaseModel):
    total_reviews: int
    awaiting_approval: int
    high_severity_issues: int
    approved_reviews: int
    status_counts: Dict[str, int]
    severity_distribution: Dict[str, int]
    category_distribution: Dict[str, int]
    recent_reviews: List[ContentItemResponse]
    recent_activity: List[AuditEventResponse]

class GovernanceInsightsResponse(BaseModel):
    most_frequent_categories: List[Dict[str, Any]]
    most_triggered_rules: List[Dict[str, Any]]
    recurring_unresolved_issues: List[Dict[str, Any]]
    approval_turnaround_summary: Dict[str, Any]
    rule_clarity_insights: List[Dict[str, Any]]
