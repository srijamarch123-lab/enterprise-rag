from sqlalchemy.orm import Session
from app.models import Document

def handle_document_versioning(db: Session, original_filename: str, owner_user_id: int | None, department: str | None = None) -> int:
    """
    Finds existing active documents with the same filename (and same owner for personal docs,
    or same department/global scope), marks them as inactive (is_active = False),
    and returns the incremented version number.
    """
    query = db.query(Document).filter(
        Document.original_filename == original_filename,
        Document.is_active == True
    )
    
    if owner_user_id is not None:
        query = query.filter(Document.owner_user_id == owner_user_id)
    else:
        query = query.filter(Document.owner_user_id == None, Document.department == department)
        
    existing = query.first()
    if existing:
        existing.is_active = False
        db.commit()
        return existing.version + 1
    return 1
