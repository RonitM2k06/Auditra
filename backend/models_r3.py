"""Round 3 tables: identity, governance policies, publishing, evidence, images, campaigns."""
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, LargeBinary, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.database import Base
from backend.models import generate_uuid, get_utc_now


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=True)  # null for demo personas (sign-in only via /auth/demo)
    is_demo = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "brand_id", name="uq_membership_user_brand"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # creator, reviewer, admin
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # sha256 of the cookie value
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class ApprovalPolicy(Base):
    __tablename__ = "approval_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    condition_type = Column(String(30), nullable=False)  # severity_at_least, claim_status, finding_category
    condition_value = Column(String(60), nullable=False)
    required_role = Column(String(20), nullable=True)  # reviewer, admin; null = any approver
    min_approvals = Column(Integer, nullable=False, default=1)
    require_evidence_confirmation = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (UniqueConstraint("content_version_id", "channel", name="uq_publication_version_channel"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    channel = Column(String(40), nullable=False, default="sandbox")
    status = Column(String(20), nullable=False, default="published")
    body_sha256 = Column(String(64), nullable=False)
    export_json = Column(Text, nullable=False)
    published_by = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    source_identifier = Column(String(120), nullable=True)
    file_format = Column(String(10), nullable=False)  # txt, md, pdf
    effective_date = Column(String(10), nullable=True)  # ISO dates, stored only when supplied
    expiry_date = Column(String(10), nullable=True)
    review_date = Column(String(10), nullable=True)
    approval_status = Column(String(20), nullable=False, default="approved")  # approved, pending, retired
    sha256 = Column(String(64), nullable=False)
    char_count = Column(Integer, nullable=False, default=0)
    uploaded_by = Column(String(100), nullable=False, default="System")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    passages = relationship("SourcePassage", back_populates="document", cascade="all, delete-orphan", order_by="SourcePassage.ordinal")


class SourcePassage(Base):
    __tablename__ = "source_passages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    section = Column(String(255), nullable=True)
    page = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)

    document = relationship("SourceDocument", back_populates="passages")


class ClaimCheck(Base):
    __tablename__ = "claim_checks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False)  # supported, unsupported, contradicted, stale, needs_review
    passage_id = Column(String(36), ForeignKey("source_passages.id", ondelete="SET NULL"), nullable=True)
    source_document_id = Column(String(36), ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True)
    passage_text = Column(Text, nullable=True)  # copy of the stored passage at check time
    retrieval_score = Column(Float, nullable=False, default=0.0)
    coverage = Column(Float, nullable=False, default=0.0)
    rationale = Column(Text, nullable=False)
    details_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, unique=True)
    mime_type = Column(String(20), nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    byte_size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    data = Column(LargeBinary, nullable=False)
    ocr_json = Column(Text, nullable=False, default="{}")
    visual_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class BrandLogo(Base):
    __tablename__ = "brand_logos"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, unique=True)
    mime_type = Column(String(20), nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    brief = Column(Text, nullable=True)  # approved campaign brief, used as the reference text
    created_by = Column(String(100), nullable=False, default="System")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class CampaignAsset(Base):
    __tablename__ = "campaign_assets"
    __table_args__ = (UniqueConstraint("campaign_id", "content_id", name="uq_campaign_asset"),)

    id = Column(String(36), primary_key=True, default=generate_uuid)
    campaign_id = Column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)


class RuleSnapshot(Base):
    __tablename__ = "rule_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    rules_json = Column(Text, nullable=False)
    policies_json = Column(Text, nullable=False, default="[]")
    sources_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)


class RuleProposal(Base):
    """A draft rulebook change. Simulated against current content; activated only by a separate admin."""
    __tablename__ = "rule_proposals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    rationale = Column(Text, nullable=True)
    changes_json = Column(Text, nullable=False)
    simulation_json = Column(Text, nullable=False)
    rulebook_fingerprint = Column(String(64), nullable=False)  # rulebook state the simulation ran against
    status = Column(String(20), nullable=False, default="proposed")  # proposed, activated, rejected
    proposed_by = Column(String(100), nullable=False)
    proposed_by_user_id = Column(String(36), nullable=False)
    decided_by = Column(String(100), nullable=True)
    decision_note = Column(Text, nullable=True)
    simulated_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
