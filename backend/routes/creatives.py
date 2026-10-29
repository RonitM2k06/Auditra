import io
import json
import re
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import vision
from backend.auth import authorize, authorize_content, current_user
from backend.database import get_db
from backend.models import AuditEvent, Brand, ContentItem, ContentVersion
from backend.models_r3 import BrandLogo, ImageAsset, User
from backend.review_pipeline import brand_palette
from backend.routes.content import get_content_item_detail
from backend.schemas import ContentItemDetailResponse

router = APIRouter(tags=["Creatives"])

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"The file is larger than {limit // 1024 // 1024} MB.")
    return data


def _ingest(data: bytes):
    try:
        img, mime = vision.validate_image(data)
    except vision.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    ocr = vision.run_ocr(img)
    if ocr["status"] != "ok":
        raise HTTPException(status_code=503, detail="The OCR engine is unavailable on this server, so the creative can't be analysed. Nothing was saved.")
    return img, mime, ocr


def _asset(version_id: str, data: bytes, img, mime: str, ocr: dict) -> ImageAsset:
    return ImageAsset(content_version_id=version_id, mime_type=mime, width=img.width, height=img.height,
                      byte_size=len(data), sha256=vision.sha256(data), data=data, ocr_json=json.dumps(ocr), visual_json="{}")


@router.post("/brands/{brand_id}/creatives", response_model=ContentItemDetailResponse, status_code=201)
async def upload_creative(
    brand_id: str,
    title: str = Form(..., min_length=1, max_length=255),
    content_type: str = Form("social_post", max_length=60),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    actor = authorize(db, user, brand_id, "content.write")
    if not title.strip():
        raise HTTPException(status_code=422, detail="Give the creative a title.")
    data = await _read_limited(file, vision.MAX_IMAGE_BYTES)
    img, mime, ocr = _ingest(data)

    item = ContentItem(brand_id=brand_id, title=title.strip(), content_type=content_type, status="draft",
                       current_version_number=1, created_by=actor.name, created_by_user_id=user.id, media_kind="image")
    db.add(item)
    db.flush()
    version = ContentVersion(content_id=item.id, version_number=1, body=ocr["text"],
                             change_summary="Uploaded creative (text extracted by OCR)", created_by=actor.name)
    db.add(version)
    db.flush()
    db.add(_asset(version.id, data, img, mime, ocr))
    db.add(AuditEvent(brand_id=brand_id, content_id=item.id, event_type="creative_uploaded", actor_name=actor.name,
                      actor_role=actor.role_label,
                      description=f"Uploaded creative '{item.title}' ({img.width}×{img.height}, {len(ocr['lines'])} text lines extracted).",
                      event_metadata=json.dumps({"version": 1, "sha256": vision.sha256(data), "ocr_lines": len(ocr["lines"])})))
    db.commit()
    return get_content_item_detail(item.id, db)


@router.post("/content/{content_id}/creative", response_model=ContentItemDetailResponse)
async def upload_revised_creative(content_id: str, file: UploadFile = File(...),
                                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, actor = authorize_content(db, user, content_id, "content.write")
    if item.media_kind != "image":
        raise HTTPException(status_code=409, detail="This item is text content; edit it in the studio instead.")
    data = await _read_limited(file, vision.MAX_IMAGE_BYTES)
    current = db.query(ContentVersion).filter(ContentVersion.content_id == item.id,
                                              ContentVersion.version_number == item.current_version_number).first()
    current_asset = db.query(ImageAsset).filter(ImageAsset.content_version_id == current.id).first() if current else None
    if current_asset and current_asset.sha256 == vision.sha256(data):
        raise HTTPException(status_code=409, detail="This image is identical to the current version.")
    img, mime, ocr = _ingest(data)
    n = item.current_version_number + 1
    version = ContentVersion(content_id=item.id, version_number=n, body=ocr["text"],
                             change_summary="Uploaded revised creative", created_by=actor.name)
    db.add(version)
    db.flush()
    db.add(_asset(version.id, data, img, mime, ocr))
    item.current_version_number = n
    if item.status == "approved":
        item.status = "draft"
    item.approved_version_id = None
    db.add(AuditEvent(brand_id=item.brand_id, content_id=item.id, event_type="creative_revised", actor_name=actor.name,
                      actor_role=actor.role_label, description=f"Uploaded a revised creative (version {n}).",
                      event_metadata=json.dumps({"version": n, "sha256": vision.sha256(data)})))
    db.commit()
    return get_content_item_detail(item.id, db)


@router.get("/content/{content_id}/versions/{version_number}/image")
def get_creative_image(content_id: str, version_number: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize_content(db, user, content_id, "workspace.view")
    version = db.query(ContentVersion).filter(ContentVersion.content_id == content_id,
                                              ContentVersion.version_number == version_number).first()
    asset = db.query(ImageAsset).filter(ImageAsset.content_version_id == version.id).first() if version else None
    if not asset:
        raise HTTPException(status_code=404, detail="No image for this version")
    return Response(content=asset.data, media_type=asset.mime_type,
                    headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


# --- Visual identity: reference logo and palette (admin) ---

class PaletteIn(BaseModel):
    colors: List[str] = Field(default_factory=list, max_length=12)


@router.get("/brands/{brand_id}/visual-identity")
def get_visual_identity(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    logo = db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first()
    return {
        "palette": brand_palette(brand),
        "extra_colors": json.loads(brand.palette_json or "[]"),
        "logo": {"width": logo.width, "height": logo.height, "url": f"/api/brands/{brand_id}/logo"} if logo else None,
    }


@router.put("/brands/{brand_id}/palette")
def set_palette(brand_id: str, payload: PaletteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    bad = [c for c in payload.colors if not HEX_RE.match(c)]
    if bad:
        raise HTTPException(status_code=422, detail=f"Not hex colours (#RRGGBB): {', '.join(bad[:3])}")
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    brand.palette_json = json.dumps([c.upper() for c in payload.colors])
    db.add(AuditEvent(brand_id=brand_id, event_type="palette_updated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Updated the approved palette ({len(payload.colors)} extra colours).",
                      event_metadata=json.dumps({"colors": payload.colors})))
    db.commit()
    return get_visual_identity(brand_id, user, db)


@router.get("/brands/{brand_id}/logo")
def get_logo(brand_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    authorize(db, user, brand_id, "workspace.view")
    logo = db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first()
    if not logo:
        raise HTTPException(status_code=404, detail="No reference logo configured")
    return Response(content=logo.data, media_type=logo.mime_type, headers={"X-Content-Type-Options": "nosniff"})


@router.post("/brands/{brand_id}/logo")
async def upload_logo(brand_id: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    actor = authorize(db, user, brand_id, "rules.manage")
    data = await _read_limited(file, 1024 * 1024)
    try:
        img, mime = vision.validate_image(data)
    except vision.ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    rec = db.query(BrandLogo).filter(BrandLogo.brand_id == brand_id).first()
    if rec:
        rec.data, rec.mime_type, rec.width, rec.height = data, mime, img.width, img.height
    else:
        db.add(BrandLogo(brand_id=brand_id, data=data, mime_type=mime, width=img.width, height=img.height))
    db.add(AuditEvent(brand_id=brand_id, event_type="logo_updated", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Set the reference logo ({img.width}×{img.height})."))
    db.commit()
    return get_visual_identity(brand_id, user, db)
