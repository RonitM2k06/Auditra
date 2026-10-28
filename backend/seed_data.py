import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend import models
from backend.models import (
    Brand, BrandRule, ApprovedClaim, ContentItem, ContentVersion,
    ReviewRun, Finding, ReviewDecision, Comment, AuditEvent
)
from backend.rule_engine import ComplianceRuleEngine
from backend.models_r3 import (
    ApprovalPolicy, BrandLogo, Campaign, CampaignAsset, ImageAsset, Membership, User,
)
import os

def seed_sample_workspace(db: Session, force_reset: bool = False) -> Brand:
    models._seed_counter = 0
    try:
        return _seed_sample_workspace(db, force_reset)
    finally:
        models._seed_counter = None

def _seed_sample_workspace(db: Session, force_reset: bool = False) -> Brand:
    # Check if Northstar sample brand already exists
    existing = db.query(Brand).filter(Brand.slug == "northstar").first()
    if existing:
        if not force_reset:
            _upgrade_round2_sample(db, existing)
            return existing
        # Delete existing sample brand to refresh cleanly
        db.delete(existing)
        db.commit()

    now = datetime.now(timezone.utc)

    # 1. Create Brand
    northstar = Brand(
        name="Northstar Cloud",
        slug="northstar",
        industry="Enterprise Cloud & Infrastructure",
        description="Northstar provides resilient mission-critical cloud governance and automation for global enterprises.",
        is_sample=True,
        primary_color="#0F9D91",
        secondary_color="#101B2D",
        created_at=now - timedelta(days=7),
        updated_at=now
    )
    db.add(northstar)
    db.flush()

    # 2. Add Rules
    rules_data = [
        {
            "name": "Absolute Outcome Guarantees Prohibited",
            "category": "prohibited_term",
            "description": "Never make absolute outcome promises. Performance depends on individual enterprise workload configurations.",
            "rule_text": "Never promise guaranteed results or 100% outcomes.",
            "match_pattern": "guarantees results",
            "suggested_replacement": "delivers proven performance gains",
            "severity": "critical",
            "source_reference": "Northstar Legal Governance Standard §4.1"
        },
        {
            "name": "Prohibit 'Risk-Free' Claims",
            "category": "prohibited_term",
            "description": "Enterprise risk must be framed with precision. 'Risk-free' is legally misleading in infrastructure.",
            "rule_text": "Do not state that any product or deployment is risk-free.",
            "match_pattern": "100% risk-free",
            "suggested_replacement": "enterprise-backed deployment assurance",
            "severity": "critical",
            "source_reference": "Northstar Legal Risk Policy §2.3"
        },
        {
            "name": "Subscriber Nomenclature: 'Members' over 'Users'",
            "category": "preferred_term",
            "description": "Refer to platform participants and ecosystem subscribers as 'members' rather than generic 'users'.",
            "rule_text": "Use 'members' or 'partners' instead of 'users'.",
            "match_pattern": "users",
            "suggested_replacement": "members",
            "severity": "medium",
            "source_reference": "Northstar Editorial Style Guide §1.2"
        },
        {
            "name": "Mandatory Performance Disclaimer",
            "category": "required_phrase",
            "description": "All customer-facing materials discussing performance improvements must include the variation disclosure.",
            "rule_text": "Mandatory disclosure: 'Results may vary based on client workload and infrastructure configurations.'",
            "match_pattern": "Results may vary based on client workload",
            "suggested_replacement": "\n\nDisclaimer: Results may vary based on client workload and infrastructure configurations.",
            "severity": "high",
            "source_reference": "Northstar Regulatory Compliance §8.4"
        },
        {
            "name": "Restricted 7-Day Performance Multipliers",
            "category": "restricted_claim",
            "description": "Unverified short-term performance promises like 'double performance in seven days' violate product accuracy policies.",
            "rule_text": "Claims promising double performance in days are prohibited without certified audit lab approval.",
            "match_pattern": "double your performance in seven days",
            "suggested_replacement": "accelerate workload efficiency by up to 34% over 90 days",
            "severity": "high",
            "source_reference": "Northstar Product Claims Manual §3.0"
        },
        {
            "name": "Tone: Avoid Sensational Clickbait",
            "category": "tone_voice",
            "description": "Maintain an objective, engineering-grounded tone. Avoid sensationalist hyperbole such as 'unbelievable secret'.",
            "rule_text": "Avoid sensational hype words and clickbait phrases.",
            "match_pattern": "unbelievable secret",
            "suggested_replacement": "verified architecture",
            "severity": "medium",
            "source_reference": "Northstar Voice & Tone Charter §2.1"
        },
        {
            "name": "Style: Excessive Exclamation Points",
            "category": "formatting_style",
            "description": "Multiple exclamation points undermine authority and violate enterprise brand editorial guidelines.",
            "rule_text": "Avoid multiple consecutive exclamation points.",
            "match_pattern": "!!!",
            "suggested_replacement": ".",
            "severity": "low",
            "source_reference": "Northstar Editorial Style Guide §5.2"
        }
    ]

    saved_rules = []
    for r in rules_data:
        rule = BrandRule(
            brand_id=northstar.id,
            name=r["name"],
            category=r["category"],
            description=r["description"],
            rule_text=r["rule_text"],
            match_pattern=r["match_pattern"],
            suggested_replacement=r["suggested_replacement"],
            severity=r["severity"],
            source_reference=r["source_reference"],
            is_active=True,
            created_at=now - timedelta(days=6)
        )
        db.add(rule)
        saved_rules.append(rule)
    db.flush()

    # 3. Add Approved Claims
    claims_data = [
        {
            "claim_statement": "Northstar accelerates enterprise workload throughput by up to 34% within 90 days of cluster optimization.",
            "topic": "Performance",
            "evidence_source": "Northstar Benchmark Report Q2 2026, audited by CloudMetric Labs.",
            "verification_date": "2026-06-30"
        },
        {
            "claim_statement": "Northstar maintains a verified 99.995% uptime SLA backed by multi-region automated failover.",
            "topic": "Reliability",
            "evidence_source": "Northstar SOC2 Type II Audit & Public SLA Registry 2026.",
            "verification_date": "2026-08-15"
        },
        {
            "claim_statement": "Over 450 Fortune 1000 organizations manage sovereign cloud workloads using Northstar.",
            "topic": "Adoption",
            "evidence_source": "Northstar Customer Reference Portal, verified October 2026.",
            "verification_date": "2026-10-01"
        }
    ]

    saved_claims = []
    for c in claims_data:
        claim = ApprovedClaim(
            brand_id=northstar.id,
            claim_statement=c["claim_statement"],
            topic=c["topic"],
            evidence_source=c["evidence_source"],
            verification_date=c["verification_date"],
            is_active=True,
            created_at=now - timedelta(days=5)
        )
        db.add(claim)
        saved_claims.append(claim)
    db.flush()

    # 4. Seed Content Item 1: Primary Demo with violations (The exact scenario from Section 22)
    demo_body_v1 = "Northstar guarantees results for every customer. Our users will double their performance in seven days. Join today and unlock the unbelievable secret to instant cloud speed!!!"

    content_demo = ContentItem(
        brand_id=northstar.id,
        title="Q4 Enterprise Cloud Promotion (Demo Scenario)",
        content_type="social_post",
        status="in_review",
        current_version_number=1,
        created_by="Alex Rivers (Growth Lead)",
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2)
    )
    db.add(content_demo)
    db.flush()

    v1 = ContentVersion(
        content_id=content_demo.id,
        version_number=1,
        body=demo_body_v1,
        change_summary="Initial copy drafted for Q4 omni-channel promotion.",
        created_by="Alex Rivers (Growth Lead)",
        created_at=now - timedelta(hours=3)
    )
    db.add(v1)
    db.flush()

    # Run deterministic compliance engine on Content 1
    engine = ComplianceRuleEngine(saved_rules, saved_claims)
    demo_findings = engine.analyze(demo_body_v1)

    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    cat_counts = {}
    for f in demo_findings:
        sev = f.severity.lower()
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        cat_counts[f.category] = cat_counts.get(f.category, 0) + 1

    risk_score = min(100, sev_counts.get("critical", 0) * 35 + sev_counts.get("high", 0) * 20 + sev_counts.get("medium", 0) * 10)

    review_run_1 = ReviewRun(
        content_id=content_demo.id,
        content_version_id=v1.id,
        brand_id=northstar.id,
        engine_type="deterministic",
        ai_status="fallback_rule_based",
        status="completed",
        risk_score=risk_score,
        summary=f"Analysis flagged {len(demo_findings)} governance issues: {sev_counts['critical']} critical, {sev_counts['high']} high risk.",
        severity_counts=json.dumps(sev_counts),
        category_breakdown=json.dumps(cat_counts),
        created_at=now - timedelta(hours=2, minutes=50)
    )
    db.add(review_run_1)
    db.flush()

    for df in demo_findings:
        f_rec = Finding(
            review_run_id=review_run_1.id,
            content_version_id=v1.id,
            rule_id=df.rule_id,
            category=df.category,
            severity=df.severity,
            matched_text=df.matched_text,
            start_offset=df.start_offset,
            end_offset=df.end_offset,
            explanation=df.explanation,
            source_reference=df.source_reference,
            suggested_correction=df.suggested_correction,
            confidence=df.confidence,
            requires_human_review=df.requires_human_review,
            finding_source=df.finding_source,
            created_at=now - timedelta(hours=2, minutes=50)
        )
        db.add(f_rec)

    # Add comments and audit events for Content 1
    db.add(Comment(
        content_id=content_demo.id,
        content_version_id=v1.id,
        author_name="Sarah Chen",
        author_role="Senior Brand Compliance Officer",
        text="Alex, please note the critical guarantee and terminology issues. Revise the copy using our approved benchmark claims before resubmitting.",
        created_at=now - timedelta(hours=2, minutes=30)
    ))

    audit_events_demo = [
        AuditEvent(
            brand_id=northstar.id,
            content_id=content_demo.id,
            event_type="draft_created",
            actor_name="Alex Rivers",
            actor_role="Growth Lead",
            description="Created content item 'Q4 Enterprise Cloud Promotion (Demo Scenario)'",
            event_metadata=json.dumps({"version": 1}),
            created_at=now - timedelta(hours=3)
        ),
        AuditEvent(
            brand_id=northstar.id,
            content_id=content_demo.id,
            event_type="analysis_run",
            actor_name="System",
            actor_role="Rule Engine",
            description=f"Automated compliance check completed. {len(demo_findings)} findings identified with risk score {risk_score}.",
            event_metadata=json.dumps({"risk_score": risk_score, "findings_count": len(demo_findings)}),
            created_at=now - timedelta(hours=2, minutes=50)
        ),
        AuditEvent(
            brand_id=northstar.id,
            content_id=content_demo.id,
            event_type="submitted_for_review",
            actor_name="Alex Rivers",
            actor_role="Growth Lead",
            description="Submitted version 1 to governance review queue.",
            event_metadata=json.dumps({"version": 1}),
            created_at=now - timedelta(hours=2, minutes=45)
        ),
        AuditEvent(
            brand_id=northstar.id,
            content_id=content_demo.id,
            event_type="comment_added",
            actor_name="Sarah Chen",
            actor_role="Senior Brand Compliance Officer",
            description="Added reviewer feedback on version 1.",
            event_metadata=json.dumps({}),
            created_at=now - timedelta(hours=2, minutes=30)
        )
    ]
    for ae in audit_events_demo:
        db.add(ae)

    # 5. Seed Content Item 2: Fully Approved Post-Correction Item
    v1_body_item2 = "Apex FinTech migrated core workloads to Northstar. Our users doubled performance instantly."
    v2_body_item2 = "Apex FinTech migrated core workloads to Northstar, achieving up to 34% workload throughput optimization within 90 days. Over 450 Fortune 1000 organizations manage sovereign cloud workloads using Northstar.\n\nDisclaimer: Results may vary based on client workload and infrastructure configurations."

    content_approved = ContentItem(
        brand_id=northstar.id,
        title="Apex FinTech Enterprise Case Study",
        content_type="blog_post",
        status="approved",
        current_version_number=2,
        created_by="Marcus Vance (Technical Writer)",
        reviewer_id="Sarah Chen (Senior Brand Compliance Officer)",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(hours=4)
    )
    db.add(content_approved)
    db.flush()

    v2_1 = ContentVersion(
        content_id=content_approved.id,
        version_number=1,
        body=v1_body_item2,
        change_summary="Initial case study draft",
        created_by="Marcus Vance (Technical Writer)",
        created_at=now - timedelta(days=2)
    )
    db.add(v2_1)

    v2_2 = ContentVersion(
        content_id=content_approved.id,
        version_number=2,
        body=v2_body_item2,
        change_summary="Substituted unverified speed claim with approved 34% benchmark claim, replaced 'users' with 'members', added mandatory infrastructure variation disclaimer.",
        created_by="Marcus Vance (Technical Writer)",
        created_at=now - timedelta(days=1)
    )
    db.add(v2_2)
    db.flush()

    # Clean review run for V2
    clean_findings = engine.analyze(v2_body_item2)
    clean_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    clean_cat = {}
    for cf in clean_findings:
        s = cf.severity.lower()
        clean_sev[s] = clean_sev.get(s, 0) + 1
        clean_cat[cf.category] = clean_cat.get(cf.category, 0) + 1

    clean_review = ReviewRun(
        content_id=content_approved.id,
        content_version_id=v2_2.id,
        brand_id=northstar.id,
        engine_type="deterministic",
        ai_status="fallback_rule_based",
        status="completed",
        risk_score=0,
        summary="Zero policy violations detected. Content complies fully with Northstar brand guidelines and approved claims.",
        severity_counts=json.dumps(clean_sev),
        category_breakdown=json.dumps(clean_cat),
        created_at=now - timedelta(days=1, hours=2)
    )
    db.add(clean_review)

    db.add(ReviewDecision(
        content_id=content_approved.id,
        content_version_id=v2_2.id,
        decision="approved",
        reviewer_name="Sarah Chen",
        reviewer_role="Senior Brand Compliance Officer",
        comments="Approved for global publication. All claims are grounded in Q2 audited benchmark data and mandatory disclaimer is verified.",
        created_at=now - timedelta(hours=4)
    ))

    db.add(AuditEvent(
        brand_id=northstar.id,
        content_id=content_approved.id,
        event_type="content_approved",
        actor_name="Sarah Chen",
        actor_role="Senior Brand Compliance Officer",
        description="Approved version 2 for multi-channel distribution.",
        event_metadata=json.dumps({"version": 2}),
        created_at=now - timedelta(hours=4)
    ))

    # 6. Seed Content Item 3: A simple draft item
    content_draft = ContentItem(
        brand_id=northstar.id,
        title="Weekly Community Digest #42",
        content_type="email",
        status="draft",
        current_version_number=1,
        created_by="Elena Rostova (Community Manager)",
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1)
    )
    db.add(content_draft)
    db.flush()

    v3_1 = ContentVersion(
        content_id=content_draft.id,
        version_number=1,
        body="Discover how Northstar members streamline hybrid cloud governance with automated policy guardrails and unified telemetry.",
        change_summary="Draft newsletter overview",
        created_by="Elena Rostova (Community Manager)",
        created_at=now - timedelta(hours=1)
    )
    db.add(v3_1)
    db.flush()

    users = _seed_people(db, northstar)
    content_demo.created_by_user_id = users["creator"].id
    content_approved.approved_version_id = v2_2.id
    for d in db.query(ReviewDecision).filter(ReviewDecision.content_id == content_approved.id).all():
        d.reviewer_user_id = users["reviewer"].id
        d.evidence_confirmed = True
    _seed_round3(db, northstar, users, now)

    db.commit()
    db.refresh(northstar)
    return northstar


SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
DEMO_PEOPLE = [
    ("creator", "alex.rivers@northstar.demo", "Alex Rivers"),
    ("reviewer", "sarah.chen@northstar.demo", "Sarah Chen"),
    ("admin", "morgan.lee@northstar.demo", "Morgan Lee"),
]


def _seed_people(db: Session, brand: Brand) -> dict:
    """Fictional demo personas. They have no password and can only sign in through /api/auth/demo."""
    out = {}
    for role, email, name in DEMO_PEOPLE:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, display_name=name, is_demo=True, password_hash=None)
            db.add(user)
            db.flush()
        db.add(Membership(user_id=user.id, brand_id=brand.id, role=role))
        out[role] = user
    db.flush()
    return out


def _read_sample(*parts) -> bytes:
    with open(os.path.join(SAMPLES, *parts), "rb") as fh:
        return fh.read()


def _seed_round3(db: Session, brand: Brand, users: dict, now) -> None:
    from backend.routes.sources import ingest_document
    from backend import vision

    brand.palette_json = json.dumps(["#FFFFFF", "#E9EEF2", "#5B6B7F"])

    # Deliberately conflicting rule (labelled) so the Brand DNA contradiction check has something real to find.
    db.add(BrandRule(
        brand_id=brand.id, name="Legacy: 'customers' -> 'users' (demo conflict)", category="preferred_term",
        description="Imported from the 2023 style guide. Demo data: this conflicts with the 'members over users' rule.",
        rule_text="Use 'users' instead of 'customers'.", match_pattern="customers", suggested_replacement="users",
        severity="low", is_active=True, source_reference="Northstar Style Guide 2023 (superseded)",
    ))

    db.add_all([
        ApprovalPolicy(brand_id=brand.id, name="Critical findings need two approvers", condition_type="severity_at_least",
                       condition_value="critical", required_role="reviewer", min_approvals=2),
        ApprovalPolicy(brand_id=brand.id, name="Contradicted claims need evidence review", condition_type="claim_status",
                       condition_value="contradicted", required_role="reviewer", require_evidence_confirmation=True),
        ApprovalPolicy(brand_id=brand.id, name="Stale evidence needs evidence review", condition_type="claim_status",
                       condition_value="stale", require_evidence_confirmation=True),
        ApprovalPolicy(brand_id=brand.id, name="Restricted claims need the compliance lead", condition_type="finding_category",
                       condition_value="restricted_claim", required_role="reviewer"),
    ])

    sources = [
        ("northstar-fact-sheet-2026.md", "Northstar Product Fact Sheet 2026", "NS-FACT-2026", "2026-01-15", "2027-01-15", None),
        ("northstar-pricing-2025.md", "Northstar Pricing Sheet 2025", "NS-PRICE-2025", "2025-01-01", "2025-12-31", None),
        ("northstar-security-overview.txt", "Security & Compliance Overview", "NS-SEC-01", None, None, "2026-03-01"),
    ]
    for fname, name, ident, eff, exp, rev in sources:
        try:
            ingest_document(db, brand.id, fname, _read_sample("sources", fname), name=name, source_identifier=ident,
                            effective_date=eff, expiry_date=exp, review_date=rev, approval_status="approved", uploaded_by="Morgan Lee")
        except (OSError, ValueError):
            pass

    try:
        logo = _read_sample("brand", "northstar-logo.png")
        img, mime = vision.validate_image(logo)
        db.add(BrandLogo(brand_id=brand.id, mime_type=mime, width=img.width, height=img.height, data=logo))
    except (OSError, ValueError):
        pass

    def text_item(title, ctype, body, minutes_ago):
        item = ContentItem(brand_id=brand.id, title=title, content_type=ctype, status="draft", current_version_number=1,
                           created_by="Alex Rivers", created_by_user_id=users["creator"].id, media_kind="text",
                           created_at=now - timedelta(minutes=minutes_ago), updated_at=now - timedelta(minutes=minutes_ago))
        db.add(item)
        db.flush()
        db.add(ContentVersion(content_id=item.id, version_number=1, body=body, change_summary="Initial draft",
                              created_by="Alex Rivers", created_at=now - timedelta(minutes=minutes_ago)))
        db.add(AuditEvent(brand_id=brand.id, content_id=item.id, event_type="draft_created", actor_name="Alex Rivers",
                          actor_role="Content Creator", description=f"Created content draft '{title}' (version 1).",
                          event_metadata=json.dumps({"version": 1}), created_at=now - timedelta(minutes=minutes_ago)))
        return item

    disclaimer = "Disclaimer: Results may vary based on client workload and infrastructure configurations."
    email = text_item("Atlas Pro launch: announcement email", "email",
                      "Atlas Pro launches November 12, 2026. Get Atlas Pro for $49 per member per month and start a 14-day free trial.\n\n"
                      "Northstar maintains a 99.995% uptime SLA backed by multi-region automated failover.\n\n" + disclaimer, 50)
    landing = text_item("Atlas Pro launch: landing page", "landing_page",
                        "Atlas Pro is available from November 14, 2026. Pricing starts at $59 per member per month.\n\n"
                        "Accelerate workload throughput by up to 34% within 90 days. Northstar is HIPAA certified for regulated workloads.\n\n" + disclaimer, 45)
    social = text_item("Atlas Pro launch: social post", "social_post",
                       "Atlas Pro is here Nov 12! Start your 14-day free trial today. Northstar guarantees results for every team.", 40)

    campaign = Campaign(brand_id=brand.id, name="Atlas Pro launch", created_by="Alex Rivers",
                        brief="Approved brief: Atlas Pro launches November 12, 2026 at $49 per member per month with a 14-day free trial. "
                              "Every asset must carry the performance disclaimer.")
    db.add(campaign)
    db.flush()
    for it in (email, landing, social):
        db.add(CampaignAsset(campaign_id=campaign.id, content_id=it.id))

    creatives = [
        ("02-violations-guarantee.png", "Migration promo social creative (sample)"),
        ("03-terminology-uptime.png", "Atlas Pro uptime banner (sample)"),
        ("01-compliant-atlas.png", "Atlas Pro launch tile (sample)"),
    ]
    for fname, title in creatives:
        try:
            data = _read_sample("creatives", fname)
            img, mime = vision.validate_image(data)
            ocr = vision.run_ocr(img)
        except (OSError, ValueError):
            continue
        if ocr["status"] != "ok":
            continue  # never seed a creative with fabricated text
        item = ContentItem(brand_id=brand.id, title=title, content_type="social_post", status="draft", current_version_number=1,
                           created_by="Alex Rivers", created_by_user_id=users["creator"].id, media_kind="image")
        db.add(item)
        db.flush()
        v = ContentVersion(content_id=item.id, version_number=1, body=ocr["text"],
                           change_summary="Uploaded creative (text extracted by OCR)", created_by="Alex Rivers")
        db.add(v)
        db.flush()
        db.add(ImageAsset(content_version_id=v.id, mime_type=mime, width=img.width, height=img.height, byte_size=len(data),
                          sha256=vision.sha256(data), data=data, ocr_json=json.dumps(ocr), visual_json="{}"))
        db.add(AuditEvent(brand_id=brand.id, content_id=item.id, event_type="creative_uploaded", actor_name="Alex Rivers",
                          actor_role="Content Creator", description=f"Uploaded creative '{title}' ({len(ocr['lines'])} text lines extracted).",
                          event_metadata=json.dumps({"version": 1})))


def _upgrade_round2_sample(db: Session, brand: Brand) -> None:
    """A Northstar workspace seeded before Round 3 has no members. Add the demo personas and
    Round 3 sample data in place, without touching the existing rows."""
    if db.query(Membership).filter(Membership.brand_id == brand.id).first():
        return
    # Random IDs here: the deterministic seed counter would collide with the rows seeded in Round 2.
    models._seed_counter = None
    now = datetime.now(timezone.utc)
    users = _seed_people(db, brand)
    for item in db.query(ContentItem).filter(ContentItem.brand_id == brand.id).all():
        if item.status == "approved" and not item.approved_version_id:
            version = db.query(ContentVersion).filter(ContentVersion.content_id == item.id,
                                                      ContentVersion.version_number == item.current_version_number).first()
            item.approved_version_id = version.id if version else None
            for d in db.query(ReviewDecision).filter(ReviewDecision.content_id == item.id).all():
                if d.reviewer_name.startswith("Sarah Chen"):
                    d.reviewer_user_id = users["reviewer"].id
    _seed_round3(db, brand, users, now)
    db.add(AuditEvent(brand_id=brand.id, event_type="workspace_upgraded", actor_name="System", actor_role="Migration",
                      description="Added Round 3 demo personas, approval policies, evidence sources, a campaign and sample creatives."))
    db.commit()
