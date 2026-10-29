"""Session authentication and workspace role checks.

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib, 310k iterations, per-user salt).
Sessions are random 256-bit tokens sent as an HttpOnly cookie; only their SHA-256 is
stored, so a database leak does not expose usable session tokens.
"""
import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AuditEvent, Brand, ContentItem, ContentVersion, Finding
from backend.models_r3 import Membership, User, UserSession

SESSION_COOKIE = "auditra_session"
SESSION_TTL = timedelta(hours=12)
PBKDF2_ITERATIONS = 310_000

ROLE_LABEL = {"creator": "Content Creator", "reviewer": "Brand Compliance Lead", "admin": "Workspace Admin"}

# Explicit permission matrix. Every protected endpoint names one of these.
PERMISSIONS = {
    "workspace.view": {"creator", "reviewer", "admin"},
    "content.write": {"creator", "admin"},           # create/edit drafts, upload creatives, apply corrections, submit
    "content.analyse": {"creator", "reviewer", "admin"},
    "content.delete": {"admin"},
    "finding.dismiss": {"reviewer", "admin"},
    "comment.write": {"creator", "reviewer", "admin"},
    "decision.record": {"reviewer", "admin"},
    "publish": {"reviewer", "admin"},
    "rules.manage": {"admin"},                       # rules, claims, sources, policies, logo, palette, members
    "campaign.manage": {"creator", "admin"},
    "simulate": {"reviewer", "admin"},
    "evidence.reverify": {"reviewer", "admin"},      # re-run checks on content that cites a stale source
    "audit.export": {"reviewer", "admin"},           # campaign audit packs (PDF + JSON manifest)
}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token_hash=_token_hash(token), expires_at=datetime.now(timezone.utc) + SESSION_TTL))
    return token


def revoke_session(db: Session, token: Optional[str]) -> None:
    if not token:
        return
    sess = db.query(UserSession).filter(UserSession.token_hash == _token_hash(token)).first()
    if sess:
        sess.revoked = True


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def user_from_request(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.query(UserSession).filter(UserSession.token_hash == _token_hash(token)).first()
    if not sess or sess.revoked or _aware(sess.expires_at) <= datetime.now(timezone.utc):
        return None
    return db.query(User).filter(User.id == sess.user_id).first()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


@dataclass
class Actor:
    user: User
    brand_id: str
    role: str

    @property
    def name(self) -> str:
        return self.user.display_name

    @property
    def role_label(self) -> str:
        return ROLE_LABEL.get(self.role, self.role)


def _deny(db: Session, user: User, brand_id: Optional[str], permission: str, role: Optional[str]) -> None:
    # Record permission failures inside a workspace the user belongs to (not for unknown workspaces,
    # which would let anyone write into other tenants' audit logs).
    if brand_id and role:
        db.add(AuditEvent(
            brand_id=brand_id,
            event_type="permission_denied",
            actor_name=user.display_name,
            actor_role=ROLE_LABEL.get(role, role),
            description=f"Blocked: {ROLE_LABEL.get(role, role)} is not allowed to perform '{permission}'.",
            event_metadata='{"permission": "%s"}' % permission,
        ))
        db.commit()
    raise HTTPException(status_code=403, detail=f"Your role in this workspace does not allow this action ({permission}).")


def authorize(db: Session, user: User, brand_id: str, permission: str) -> Actor:
    membership = db.query(Membership).filter(Membership.user_id == user.id, Membership.brand_id == brand_id).first()
    if not membership:
        # Same response for "does not exist" and "not a member", so workspace IDs cannot be probed.
        raise HTTPException(status_code=404, detail="Workspace not found")
    if membership.role not in PERMISSIONS[permission]:
        _deny(db, user, brand_id, permission, membership.role)
    return Actor(user=user, brand_id=brand_id, role=membership.role)


def authorize_content(db: Session, user: User, content_id: str, permission: str):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    membership = db.query(Membership).filter(Membership.user_id == user.id, Membership.brand_id == item.brand_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Content item not found")
    if membership.role not in PERMISSIONS[permission]:
        _deny(db, user, item.brand_id, permission, membership.role)
    return item, Actor(user=user, brand_id=item.brand_id, role=membership.role)


def authorize_finding(db: Session, user: User, finding_id: str, permission: str):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    version = db.query(ContentVersion).filter(ContentVersion.id == finding.content_version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Finding not found")
    item, actor = authorize_content(db, user, version.content_id, permission)
    return finding, item, actor


def brand_exists(db: Session, brand_id: str) -> bool:
    return db.query(Brand.id).filter(Brand.id == brand_id).first() is not None
