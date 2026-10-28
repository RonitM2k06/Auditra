import json
import os
import re
import time
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import (
    ROLE_LABEL, SESSION_COOKIE, SESSION_TTL, authorize, create_session, current_user,
    hash_password, revoke_session, user_from_request, verify_password,
)
from backend.database import get_db
from backend.models import AuditEvent, Brand
from backend.models_r3 import Membership, User

router = APIRouter(tags=["Authentication"])

DEMO_PERSONAS = {
    "creator": "alex.rivers@northstar.demo",
    "reviewer": "sarah.chen@northstar.demo",
    "admin": "morgan.lee@northstar.demo",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Best-effort brute-force throttle (per process; serverless instances do not share it).
_failures: dict = defaultdict(list)
MAX_FAILURES, WINDOW_SECONDS = 8, 300


def demo_login_enabled() -> bool:
    return os.getenv("AUDITRA_DEMO_LOGIN", "true").lower() != "false"


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=200)


class RegisterRequest(LoginRequest):
    display_name: str = Field(..., min_length=2, max_length=100)


class DemoLoginRequest(BaseModel):
    persona: str


class MemberAdd(BaseModel):
    email: str = Field(..., max_length=255)
    role: str


class MemberUpdate(BaseModel):
    role: str


def _set_cookie(request: Request, response: Response, token: str) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(
        SESSION_COOKIE, token, max_age=int(SESSION_TTL.total_seconds()),
        httponly=True, secure=secure, samesite="lax", path="/",
    )


def _me(db: Session, user: User) -> dict:
    memberships = db.query(Membership, Brand).join(Brand, Brand.id == Membership.brand_id).filter(Membership.user_id == user.id).all()
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_demo": user.is_demo,
        "memberships": [
            {"brand_id": b.id, "brand_name": b.name, "role": m.role, "role_label": ROLE_LABEL[m.role]}
            for m, b in memberships
        ],
    }


def _audit_all(db: Session, user: User, event_type: str, description: str) -> None:
    for m in db.query(Membership).filter(Membership.user_id == user.id).all():
        db.add(AuditEvent(brand_id=m.brand_id, event_type=event_type, actor_name=user.display_name,
                          actor_role=ROLE_LABEL[m.role], description=description))


@router.get("/auth/config")
def auth_config():
    return {"demo_login": demo_login_enabled(), "demo_personas": list(DEMO_PERSONAS) if demo_login_enabled() else []}


@router.get("/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _me(db, user)


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    now = time.time()
    _failures[email] = [t for t in _failures[email] if now - t < WINDOW_SECONDS]
    if len(_failures[email]) >= MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Wait a few minutes and try again.")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        _failures[email].append(now)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    _failures.pop(email, None)
    token = create_session(db, user)
    _audit_all(db, user, "user_login", f"{user.display_name} signed in.")
    db.commit()
    _set_cookie(request, response, token)
    return _me(db, user)


@router.post("/auth/register", status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    if email.endswith(".demo"):
        raise HTTPException(status_code=422, detail="This email domain is reserved for demo personas.")
    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Use a password of at least 10 characters.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    token = create_session(db, user)
    db.commit()
    _set_cookie(request, response, token)
    return _me(db, user)


@router.post("/auth/demo")
def demo_login(payload: DemoLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Signs in as one of the fictional Northstar personas. They are members of the demo workspace only."""
    if not demo_login_enabled():
        raise HTTPException(status_code=404, detail="Demo sign-in is disabled on this deployment.")
    email = DEMO_PERSONAS.get(payload.persona)
    if not email:
        raise HTTPException(status_code=422, detail="Unknown demo persona.")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        from backend.seed_data import seed_sample_workspace
        seed_sample_workspace(db)
        user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=503, detail="The demo workspace is not available.")
    token = create_session(db, user)
    _audit_all(db, user, "user_login", f"{user.display_name} signed in (demo persona).")
    db.commit()
    _set_cookie(request, response, token)
    return _me(db, user)


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user = user_from_request(request, db)
    revoke_session(db, request.cookies.get(SESSION_COOKIE))
    if user:
        _audit_all(db, user, "user_logout", f"{user.display_name} signed out.")
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


# --- Workspace members (admin only) ---

def _member_rows(db: Session, brand_id: str) -> List[dict]:
    rows = db.query(Membership, User).join(User, User.id == Membership.user_id).filter(Membership.brand_id == brand_id).all()
    return [{"user_id": u.id, "email": u.email, "display_name": u.display_name, "role": m.role,
             "role_label": ROLE_LABEL[m.role], "is_demo": u.is_demo} for m, u in rows]


@router.get("/brands/{brand_id}/members")
def list_members(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    return _member_rows(db, brand_id)


@router.post("/brands/{brand_id}/members", status_code=201)
def add_member(brand_id: str, payload: MemberAdd, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    if payload.role not in ROLE_LABEL:
        raise HTTPException(status_code=422, detail="Role must be creator, reviewer or admin.")
    target = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not target:
        raise HTTPException(status_code=404, detail="No account uses that email. Ask them to create an account first.")
    if db.query(Membership).filter(Membership.user_id == target.id, Membership.brand_id == brand_id).first():
        raise HTTPException(status_code=409, detail="That person is already a member of this workspace.")
    db.add(Membership(user_id=target.id, brand_id=brand_id, role=payload.role))
    db.add(AuditEvent(brand_id=brand_id, event_type="member_added", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Added {target.display_name} as {ROLE_LABEL[payload.role]}.",
                      event_metadata=json.dumps({"user_id": target.id, "role": payload.role})))
    db.commit()
    return _member_rows(db, brand_id)


def _admin_count(db: Session, brand_id: str) -> int:
    return db.query(Membership).filter(Membership.brand_id == brand_id, Membership.role == "admin").count()


@router.put("/brands/{brand_id}/members/{user_id}")
def update_member(brand_id: str, user_id: str, payload: MemberUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    if payload.role not in ROLE_LABEL:
        raise HTTPException(status_code=422, detail="Role must be creator, reviewer or admin.")
    m = db.query(Membership).filter(Membership.user_id == user_id, Membership.brand_id == brand_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.role == "admin" and payload.role != "admin" and _admin_count(db, brand_id) <= 1:
        raise HTTPException(status_code=409, detail="A workspace needs at least one admin.")
    old = m.role
    m.role = payload.role
    db.add(AuditEvent(brand_id=brand_id, event_type="member_role_changed", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Changed a member's role from {ROLE_LABEL[old]} to {ROLE_LABEL[payload.role]}.",
                      event_metadata=json.dumps({"user_id": user_id, "from": old, "to": payload.role})))
    db.commit()
    return _member_rows(db, brand_id)


@router.delete("/brands/{brand_id}/members/{user_id}")
def remove_member(brand_id: str, user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    m = db.query(Membership).filter(Membership.user_id == user_id, Membership.brand_id == brand_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.role == "admin" and _admin_count(db, brand_id) <= 1:
        raise HTTPException(status_code=409, detail="A workspace needs at least one admin.")
    db.delete(m)
    db.add(AuditEvent(brand_id=brand_id, event_type="member_removed", actor_name=actor.name, actor_role=actor.role_label,
                      description="Removed a member from the workspace.", event_metadata=json.dumps({"user_id": user_id})))
    db.commit()
    return _member_rows(db, brand_id)
