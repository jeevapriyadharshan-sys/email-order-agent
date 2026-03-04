from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EmailMessage, HumanReview, EmailStatus
from ..schemas import ReviewUpdateIn
from ..worker import process_email_task
from ..auth import require_role, get_current_user

router = APIRouter(prefix="/review", tags=["review"])

REQUIRED_FIELDS = [
    "customer_name",
    "weight_kg",
    "pickup_location",
    "drop_location",
    "pickup_time_window",
]

def compute_missing(extracted: dict) -> list:
    missing = []
    extracted = extracted or {}
    for k in REQUIRED_FIELDS:
        v = extracted.get(k)
        if v is None:
            missing.append(k)
        elif isinstance(v, str) and not v.strip():
            missing.append(k)
    return missing


@router.get("/queue")
def review_queue(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Only those still needing review
    emails = (
        db.query(EmailMessage)
        .filter(EmailMessage.status == EmailStatus.NEEDS_HUMAN_REVIEW)
        .order_by(EmailMessage.received_at.desc())
        .all()
    )
    return emails


@router.post("/{email_id}/submit")
def submit_review(
    email_id: int,
    payload: ReviewUpdateIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("admin", "reviewer"))
):
    em = db.query(EmailMessage).get(email_id)
    if not em:
        raise HTTPException(status_code=404, detail="Email not found")

    # Merge proposed fields into extracted
    merged = {**(em.extracted or {}), **(payload.proposed_fields or {})}
    em.extracted = merged

    # Recompute missing fields properly (IMPORTANT)
    em.missing_fields = compute_missing(em.extracted)

    # Upsert human review record
    hr = db.query(HumanReview).filter(HumanReview.email_id == email_id).first()
    if not hr:
        hr = HumanReview(email_id=email_id)

    hr.proposed_fields = payload.proposed_fields or {}
    hr.reviewer = payload.reviewer or ""
    hr.approved = True

    # Update status based on completeness
    if len(em.missing_fields) == 0:
        em.status = EmailStatus.READY_TO_CONFIRM
    else:
        em.status = EmailStatus.NEEDS_HUMAN_REVIEW

    db.add(em)
    db.add(hr)
    db.commit()

    # If complete, continue pipeline
    if em.status == EmailStatus.READY_TO_CONFIRM:
        process_email_task.delay(email_id)

    return {"ok": True, "status": em.status, "missing_fields": em.missing_fields}