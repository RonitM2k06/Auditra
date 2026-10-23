import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def get_utc_now():
    return datetime.now(timezone.utc)

class Brand(Base):
    __tablename__ = "brands"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, unique=True, index=True)
    industry = Column(String(100), nullable=False, default="Technology")
    description = Column(Text, nullable=True)
    is_sample = Column(Boolean, default=False, nullable=False)
    primary_color = Column(String(20), default="#0F9D91")
    secondary_color = Column(String(20), default="#101B2D")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    rules = relationship("BrandRule", back_populates="brand", cascade="all, delete-orphan")
    approved_claims = relationship("ApprovedClaim", back_populates="brand", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="brand", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="brand", cascade="all, delete-orphan")


class BrandRule(Base):
    __tablename__ = "brand_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(60), nullable=False, index=True)  # tone_voice, preferred_term, prohibited_term, required_phrase, approved_claim, restricted_claim, formatting_style
    description = Column(Text, nullable=False)
    rule_text = Column(Text, nullable=False)
    match_pattern = Column(String(500), nullable=True)  # phrase or pattern to match
    suggested_replacement = Column(String(500), nullable=True)
    severity = Column(String(20), nullable=False, default="medium")  # critical, high, medium, low
    is_active = Column(Boolean, default=True, nullable=False)
    source_reference = Column(String(255), nullable=True)  # e.g., Northstar Brand Book §4.1
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    brand = relationship("Brand", back_populates="rules")
    findings = relationship("Finding", back_populates="rule")


class ApprovedClaim(Base):
    __tablename__ = "approved_claims"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_statement = Column(Text, nullable=False)
    topic = Column(String(100), nullable=False, default="General")
    evidence_source = Column(String(255), nullable=False)
    verification_date = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    brand = relationship("Brand", back_populates="approved_claims")


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content_type = Column(String(60), nullable=False, default="social_post")  # social_post, advertisement, email, landing_page, announcement, blog_post
    status = Column(String(30), nullable=False, default="draft")  # draft, in_review, changes_requested, approved, rejected
    current_version_number = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), default="Creator", nullable=False)
    reviewer_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    brand = relationship("Brand", back_populates="content_items")
    versions = relationship("ContentVersion", back_populates="content_item", cascade="all, delete-orphan", order_by="desc(ContentVersion.version_number)")
    comments = relationship("Comment", back_populates="content_item", cascade="all, delete-orphan", order_by="asc(Comment.created_at)")
    decisions = relationship("ReviewDecision", back_populates="content_item", cascade="all, delete-orphan", order_by="desc(ReviewDecision.created_at)")
    audit_events = relationship("AuditEvent", back_populates="content_item", cascade="all, delete-orphan")


class ContentVersion(Base):
    __tablename__ = "content_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    body = Column(Text, nullable=False)
    change_summary = Column(String(255), nullable=True)
    created_by = Column(String(100), default="Creator", nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    content_item = relationship("ContentItem", back_populates="versions")
    review_runs = relationship("ReviewRun", back_populates="content_version", cascade="all, delete-orphan", order_by="desc(ReviewRun.created_at)")
    findings = relationship("Finding", back_populates="content_version", cascade="all, delete-orphan")


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    engine_type = Column(String(30), nullable=False, default="deterministic")  # deterministic, hybrid_ai
    ai_status = Column(String(30), nullable=False, default="fallback_rule_based")  # configured, fallback_rule_based, failed, skipped
    status = Column(String(30), nullable=False, default="completed")  # completed, failed
    risk_score = Column(Integer, default=0, nullable=False)  # 0 to 100
    summary = Column(Text, nullable=True)
    severity_counts = Column(Text, nullable=False, default="{}")  # JSON string
    category_breakdown = Column(Text, nullable=False, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    content_version = relationship("ContentVersion", back_populates="review_runs")
    findings = relationship("Finding", back_populates="review_run", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    review_run_id = Column(String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String(36), ForeignKey("brand_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(60), nullable=False)
    severity = Column(String(20), nullable=False)  # critical, high, medium, low
    matched_text = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    explanation = Column(Text, nullable=False)
    source_reference = Column(String(255), nullable=True)
    suggested_correction = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    requires_human_review = Column(Boolean, default=False, nullable=False)
    is_applied = Column(Boolean, default=False, nullable=False)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    finding_source = Column(String(30), default="deterministic", nullable=False)  # deterministic, ai_assisted
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    review_run = relationship("ReviewRun", back_populates="findings")
    content_version = relationship("ContentVersion", back_populates="findings")
    rule = relationship("BrandRule", back_populates="findings")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    decision = Column(String(30), nullable=False)  # approved, changes_requested, rejected
    reviewer_name = Column(String(100), nullable=False)
    reviewer_role = Column(String(100), nullable=False, default="Brand Reviewer")
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    content_item = relationship("ContentItem", back_populates="decisions")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    content_version_id = Column(String(36), ForeignKey("content_versions.id", ondelete="CASCADE"), nullable=True)
    author_name = Column(String(100), nullable=False)
    author_role = Column(String(100), nullable=False, default="Reviewer")
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    content_item = relationship("ContentItem", back_populates="comments")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    brand_id = Column(String(36), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    content_id = Column(String(36), ForeignKey("content_items.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = Column(String(60), nullable=False, index=True)
    actor_name = Column(String(100), nullable=False, default="System")
    actor_role = Column(String(100), nullable=False, default="Operator")
    description = Column(Text, nullable=False)
    event_metadata = Column(Text, nullable=True, default="{}")  # JSON string
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    brand = relationship("Brand", back_populates="audit_events")
    content_item = relationship("ContentItem", back_populates="audit_events")
