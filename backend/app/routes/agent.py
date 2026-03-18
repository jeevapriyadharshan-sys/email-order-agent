from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
from ..db import get_db
from ..models import AgentState
from ..auth import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


def _get_state(db: Session) -> AgentState:
    st = db.query(AgentState).first()
    if not st:
        st = AgentState(enabled=False)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


@router.get("/status")
def status(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    st = _get_state(db)
    return {"enabled": bool(st.enabled), "updated_at": st.updated_at}


@router.post("/start")
def start(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    st = _get_state(db)
    st.enabled = True
    st.updated_at = datetime.utcnow()
    flag_modified(st, "enabled")
    db.add(st)
    db.commit()
    db.refresh(st)
    return {"ok": True, "enabled": bool(st.enabled)}


@router.post("/stop")
def stop(db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    st = _get_state(db)
    st.enabled = False
    st.updated_at = datetime.utcnow()
    flag_modified(st, "enabled")
    db.add(st)
    db.commit()
    db.refresh(st)
    return {"ok": True, "enabled": bool(st.enabled)}