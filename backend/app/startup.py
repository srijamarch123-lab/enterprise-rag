import bcrypt
import os

def create_default_admin():
    try:
        from app.database import SessionLocal
        from app.models import User, UserRole
        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.email == "admin@company.com").first()
            if not existing:
                user = User(
                    email="admin@company.com",
                    hashed_password=bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode(),
                    full_name="Admin",
                    role=UserRole.admin,
                    is_active=True,
                    token_version=0
                )
                db.add(user)
                db.commit()
                print("Default admin created: admin@company.com / admin1234")
            else:
                print("Admin already exists")
        finally:
            db.close()
    except Exception as e:
        print(f"Admin creation skipped: {e}")


def reset_stuck_documents():
    try:
        from app.database import SessionLocal
        from app.models import Document, DocumentStatus, Chunk
        db = SessionLocal()
        try:
            stuck_docs = db.query(Document).filter(
                Document.status.in_([
                    DocumentStatus.extracting,
                    DocumentStatus.chunking,
                    DocumentStatus.embedding
                ])
            ).all()
            if stuck_docs:
                for doc in stuck_docs:
                    chunk_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
                    if not doc.extracted_text:
                        doc.status = DocumentStatus.pending
                        doc.extraction_error = "Interrupted during extraction (server restarted)"
                    elif chunk_count == 0:
                        doc.status = DocumentStatus.extracted
                        doc.extraction_error = "Interrupted during chunking (server restarted)"
                    else:
                        doc.status = DocumentStatus.chunked
                        doc.extraction_error = "Interrupted during embedding (server restarted)"
                db.commit()
                print(f"Successfully reset {len(stuck_docs)} stuck documents.")
        finally:
            db.close()
    except Exception as e:
        print(f"Stuck documents reset skipped: {e}")
