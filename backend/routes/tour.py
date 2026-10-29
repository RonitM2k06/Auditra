"""Guided judge tour: fixture discovery and a safe recovery path.

The tour itself runs in the browser and drives the normal screens and endpoints, so every
guard (roles, author/approver separation, approval reset, publishing checks) still applies.
This module only answers "which fictional Northstar asset should the tour use?" and, when the
seeded one has already been worked on, creates a clearly labelled copy of the fixture text.
Nothing here deletes or resets records.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import authorize, current_user
from backend.database import get_db
from backend.models import AuditEvent, Brand, ContentItem, ContentVersion
from backend.models_r3 import Campaign, CampaignAsset, User
from backend.seed_data import ATLAS_CAMPAIGN_NAME, ATLAS_LANDING_BODY, ATLAS_LANDING_TITLE

router = APIRouter(tags=["Guided tour"])

COPY_PREFIX = f"{ATLAS_LANDING_TITLE} (tour copy"


def _sample_brand(db: Session, brand_id: str) -> Brand:
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand or not brand.is_sample or brand.slug != "northstar":
        raise HTTPException(status_code=404, detail="The guided tour runs only in the fictional Northstar demo workspace.")
    return brand


def _untouched(item: ContentItem) -> bool:
    # The story starts from version 1 in draft. Anything else means someone already worked on it.
    return item.status == "draft" and item.current_version_number == 1


def _asset_dict(item: ContentItem, kind: str) -> dict:
    return {"id": item.id, "title": item.title, "status": item.status, "version": item.current_version_number, "kind": kind}


def tour_status(db: Session, brand_id: str) -> dict:
    campaign = db.query(Campaign).filter(Campaign.brand_id == brand_id, Campaign.name == ATLAS_CAMPAIGN_NAME).first()
    if not campaign:
        return {"ready": False, "campaign": None, "asset": None, "problem": "missing_campaign",
                "message": f"The fictional '{ATLAS_CAMPAIGN_NAME}' campaign is not in this workspace. A workspace admin can restore "
                           "the demo data from Settings → Reset demo workspace (this affects everyone using the demo)."}
    member_ids = [a.content_id for a in db.query(CampaignAsset).filter(CampaignAsset.campaign_id == campaign.id).all()]
    items = db.query(ContentItem).filter(ContentItem.id.in_(member_ids)).order_by(ContentItem.created_at).all() if member_ids else []
    camp = {"id": campaign.id, "name": campaign.name, "brief": campaign.brief, "asset_count": len(items)}

    seeded = next((i for i in items if i.title == ATLAS_LANDING_TITLE), None)
    if seeded and _untouched(seeded):
        return {"ready": True, "campaign": camp, "asset": _asset_dict(seeded, "seeded"), "problem": None, "message": None}
    copy = next((i for i in items if i.title.startswith(COPY_PREFIX) and _untouched(i)), None)
    if copy:
        return {"ready": True, "campaign": camp, "asset": _asset_dict(copy, "tour_copy"), "problem": None, "message": None}
    if seeded:
        msg = (f"The seeded landing page is already at version {seeded.current_version_number} ({seeded.status.replace('_', ' ')}), "
               "so its original violations are no longer on the current version. Create a labelled tour copy of the fictional "
               "fixture text to run the story again. Existing records are not changed.")
    else:
        msg = "The seeded landing page is no longer in the campaign. Create a labelled tour copy of the fictional fixture text to continue."
    return {"ready": False, "campaign": camp, "asset": _asset_dict(seeded, "seeded") if seeded else None,
            "problem": "asset_used" if seeded else "missing_asset", "message": msg}


@router.get("/brands/{brand_id}/tour")
def get_tour_status(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    _sample_brand(db, brand_id)
    return tour_status(db, brand_id)


@router.post("/brands/{brand_id}/tour/copy", status_code=201)
def create_tour_copy(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "content.write")
    _sample_brand(db, brand_id)
    status = tour_status(db, brand_id)
    if status["ready"]:
        return status  # an untouched asset already exists; never pile up copies
    campaign: Optional[Campaign] = db.query(Campaign).filter(Campaign.brand_id == brand_id, Campaign.name == ATLAS_CAMPAIGN_NAME).first()
    if not campaign:
        raise HTTPException(status_code=409, detail=status["message"])
    n = db.query(ContentItem).filter(ContentItem.brand_id == brand_id, ContentItem.title.like(f"{COPY_PREFIX}%")).count() + 1
    item = ContentItem(brand_id=brand_id, title=f"{COPY_PREFIX} {n})", content_type="landing_page", status="draft",
                       current_version_number=1, created_by=actor.name, created_by_user_id=user.id, media_kind="text")
    db.add(item)
    db.flush()
    db.add(ContentVersion(content_id=item.id, version_number=1, body=ATLAS_LANDING_BODY,
                          change_summary="Guided tour copy of the fictional Atlas Pro landing page fixture", created_by=actor.name))
    db.add(CampaignAsset(campaign_id=campaign.id, content_id=item.id))
    db.add(AuditEvent(brand_id=brand_id, content_id=item.id, event_type="draft_created", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Created '{item.title}' from the fictional tour fixture (version 1) and added it to '{campaign.name}'.",
                      event_metadata=json.dumps({"version": 1, "tour_copy": True})))
    db.commit()
    return tour_status(db, brand_id)
