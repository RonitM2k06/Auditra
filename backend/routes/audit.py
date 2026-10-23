import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import AuditEvent
from backend.schemas import AuditEventResponse

router = APIRouter(prefix="/brands/{brand_id}", tags=["Audit Trail"])

@router.get("/audit", response_model=List[AuditEventResponse])
def get_audit_trail(
    brand_id: str,
    content_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(AuditEvent).filter(AuditEvent.brand_id == brand_id)
    if content_id:
        query = query.filter(AuditEvent.content_id == content_id)
    if event_type:
        query = query.filter(AuditEvent.event_type == event_type)

    events = query.order_by(AuditEvent.created_at.desc()).limit(limit).all()

    results = []
    for e in events:
        meta_dict = None
        if e.event_metadata:
            try:
                meta_dict = json.loads(e.event_metadata)
            except Exception:
                meta_dict = {}

        results.append(
            AuditEventResponse(
                id=e.id,
                brand_id=e.brand_id,
                content_id=e.content_id,
                event_type=e.event_type,
                actor_name=e.actor_name,
                actor_role=e.actor_role,
                description=e.description,
                event_metadata=meta_dict,
                created_at=e.created_at
            )
        )
    return results
