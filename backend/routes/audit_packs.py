import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend import audit_pack
from backend.auth import authorize, current_user
from backend.database import get_db
from backend.models import AuditEvent
from backend.models_r3 import AuditPackExport, Campaign, User

router = APIRouter(tags=["Audit packs"])


def _campaign(db: Session, user: User, campaign_id: str):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c, authorize(db, user, c.brand_id, "audit.export")


def _export(db: Session, user: User, export_id: str) -> AuditPackExport:
    e = db.query(AuditPackExport).filter(AuditPackExport.id == export_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Export not found")
    authorize(db, user, e.brand_id, "audit.export")
    return e


def _summary(e: AuditPackExport) -> dict:
    m = json.loads(e.manifest_json)
    return {"id": e.id, "campaign_id": e.campaign_id, "created_by": e.created_by, "created_at": audit_pack.ts(e.created_at),
            "manifest_sha256": e.manifest_sha256, "final_chain_hash": e.final_chain_hash, "verification": e.verification_status,
            "summary": m["integrity"]["summary"], "checks": m["integrity"]["checks"], "limitations": m["limitations"],
            "event_count": m["audit_events"]["count"], "asset_count": len(m["assets"]),
            "json_url": f"/api/audit-packs/{e.id}/manifest.json", "pdf_url": f"/api/audit-packs/{e.id}/report.pdf"}


def _filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")[:60] or "campaign"


@router.post("/campaigns/{campaign_id}/audit-packs", status_code=201)
def create_audit_pack(campaign_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Builds one snapshot, renders both the JSON manifest and the PDF from it, and stores them together."""
    campaign, actor = _campaign(db, user, campaign_id)
    previous = (db.query(AuditPackExport).filter(AuditPackExport.campaign_id == campaign.id)
                .order_by(AuditPackExport.created_at.desc()).first())
    export_id = str(uuid.uuid4())
    manifest = audit_pack.build_manifest(db, campaign, actor.name, export_id, previous=previous)
    check = audit_pack.verify_manifest(manifest)
    if not check["valid"]:  # the builder and the verifier disagree: refuse rather than ship a pack that does not verify
        raise HTTPException(status_code=500, detail="The generated manifest failed self-verification: " + "; ".join(check["problems"]))
    try:
        pdf = audit_pack.render_pdf(manifest)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"The PDF report could not be generated ({exc.__class__.__name__}). No export was stored.")
    hashes = {e["event"]["id"]: audit_pack.sha256(audit_pack.canonical(e["event"])) for e in manifest["audit_events"]["chain"]}
    row = AuditPackExport(id=export_id, brand_id=campaign.brand_id, campaign_id=campaign.id, created_by=actor.name,
                          manifest_json=audit_pack.canonical(manifest), manifest_sha256=manifest["manifest_sha256"], pdf=pdf,
                          final_chain_hash=manifest["integrity"]["final_chain_hash"], event_hashes_json=json.dumps(hashes),
                          verification_status=manifest["integrity"]["verification"])
    db.add(row)
    db.add(AuditEvent(brand_id=campaign.brand_id, event_type="audit_pack_exported", actor_name=actor.name, actor_role=actor.role_label,
                      description=f"Exported an audit pack for campaign '{campaign.name}' ({manifest['audit_events']['count']} events, "
                                  f"verification: {manifest['integrity']['verification']}).",
                      event_metadata=json.dumps({"export_id": export_id, "campaign_id": campaign.id,
                                                 "manifest_sha256": manifest["manifest_sha256"],
                                                 "final_chain_hash": manifest["integrity"]["final_chain_hash"]})))
    db.commit()
    db.refresh(row)
    return _summary(row)


@router.get("/campaigns/{campaign_id}/audit-packs")
def list_audit_packs(campaign_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign, _ = _campaign(db, user, campaign_id)
    rows = db.query(AuditPackExport).filter(AuditPackExport.campaign_id == campaign.id).order_by(AuditPackExport.created_at.desc()).all()
    return [_summary(r) for r in rows]


@router.get("/audit-packs/{export_id}/manifest.json")
def download_manifest(export_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = _export(db, user, export_id)
    name = _filename(json.loads(e.manifest_json)["campaign"]["name"])
    return Response(e.manifest_json.encode("utf-8"), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="auditra-{name}-{e.id[:8]}.json"'})


@router.get("/audit-packs/{export_id}/report.pdf")
def download_pdf(export_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    e = _export(db, user, export_id)
    name = _filename(json.loads(e.manifest_json)["campaign"]["name"])
    return Response(e.pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="auditra-{name}-{e.id[:8]}.pdf"'})
