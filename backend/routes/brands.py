import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Brand, AuditEvent
from backend.schemas import BrandCreate, BrandUpdate, BrandResponse
from backend.seed_data import seed_sample_workspace

router = APIRouter(prefix="/brands", tags=["Brands"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    return re.sub(r'[\s_]+', '-', re.sub(r'[^\w\s-]', '', text))

@router.get("", response_model=List[BrandResponse])
def get_brands(db: Session = Depends(get_db)):
    brands = db.query(Brand).order_by(Brand.created_at.desc()).all()
    # If no brands exist at all, auto-seed the sample workspace so judges immediately have Northstar ready
    if not brands:
        sample = seed_sample_workspace(db)
        return [sample]
    return brands

@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
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
        is_sample=payload.is_sample,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color
    )
    db.add(brand)
    db.flush()

    db.add(AuditEvent(
        brand_id=brand.id,
        event_type="brand_created",
        actor_name="Administrator",
        actor_role="Admin",
        description=f"Created brand workspace '{brand.name}'."
    ))
    db.commit()
    db.refresh(brand)
    return brand

@router.get("/{brand_id}", response_model=BrandResponse)
def get_brand(brand_id: str, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.put("/{brand_id}", response_model=BrandResponse)
def update_brand(brand_id: str, payload: BrandUpdate, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(brand, key, value)

    db.add(AuditEvent(
        brand_id=brand.id,
        event_type="brand_updated",
        actor_name="Administrator",
        actor_role="Admin",
        description=f"Updated brand settings for '{brand.name}'."
    ))
    db.commit()
    db.refresh(brand)
    return brand

@router.post("/sample/reset", response_model=BrandResponse)
def reset_sample_brand(db: Session = Depends(get_db)):
    """Re-seeds or resets the official 'Northstar' demo brand workspace."""
    sample = seed_sample_workspace(db, force_reset=True)
    return sample
