"""POST /process-all — extract (with OCR retry), chunk, and embed all stored documents."""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.database import get_db
from app.dependencies.rbac import require_manager_or_above
from app.models import Document
from app.services.process_all import process_all_documents

from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["processing"])


def _run():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        process_all_documents(db)
    finally:
        db.close()


@router.post("/process-all", dependencies=[Depends(require_manager_or_above)])
def process_all(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Run in background because it can take long.
    background_tasks.add_task(_run)

    # Immediate response: provide counts for current state.
    total = db.query(Document).count()
    return {"status": "queued", "total_documents": total}

