import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Brand, AuditEvent
from backend.schemas import BrandCreate, BrandUpdate, BrandResponse
from backend.seed_data import seed_sample_workspace
from backend.auth import authorize, current_user, ROLE_LABEL
from backend.models_r3 import Membership, User

router = APIRouter(prefix="/brands", tags=["Brands"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    return re.sub(r'[\s_]+', '-', re.sub(r'[^\w\s-]', '', text))

@router.get("", response_model=List[BrandResponse])
def get_brands(user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Only workspaces the signed-in user belongs to.
    return (
        db.query(Brand).join(Membership, Membership.brand_id == Brand.id)
        .filter(Membership.user_id == user.id).order_by(Brand.created_at.desc()).all()
    )

@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(payload: BrandCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    base_slug = payload.slug or slugify(payload.name)
    slug = base_slug
    counter = 1
    while db.query(Brand).filter(Brand.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    brand = Brand(
        name=payload.name,
        slug=slug,
        industry=payload.industry,
        description=payload.description,
        is_sample=False,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color
    )
    db.add(brand)
    db.flush()
    # The creator administers the new workspace.
    db.add(Membership(user_id=user.id, brand_id=brand.id, role="admin"))

    db.add(AuditEvent(
        brand_id=brand.id,
        event_type="brand_created",
        actor_name=user.display_name,
        actor_role=ROLE_LABEL["admin"],
        description=f"Created brand workspace '{brand.name}'."
    ))
    db.commit()
    db.refresh(brand)
    return brand

@router.get("/{brand_id}", response_model=BrandResponse)
def get_brand(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.put("/{brand_id}", response_model=BrandResponse)
def update_brand(brand_id: str, payload: BrandUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("is_sample", None)
    update_data.pop("slug", None)
    for key, value in update_data.items():
        setattr(brand, key, value)

    db.add(AuditEvent(
        brand_id=brand.id,
        event_type="brand_updated",
        actor_name=actor.name,
        actor_role=actor.role_label,
        description=f"Updated brand settings for '{brand.name}'."
    ))
    db.commit()
    db.refresh(brand)
    return brand

@router.post("/sample/reset", response_model=BrandResponse)
def reset_sample_brand(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Resets the fictional Northstar demo workspace. Only its admins may do this."""
    existing = db.query(Brand).filter(Brand.slug == "northstar", Brand.is_sample == True).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Workspace not found")
    authorize(db, user, existing.id, "rules.manage")
    sample = seed_sample_workspace(db, force_reset=True)
    return sample
