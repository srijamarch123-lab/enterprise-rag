from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.routes.search_v1 as search_v1
from app.database import Base
from app.models import AccessLevel, Chunk, Document, User, UserRole
from app.routes.search_v1 import SearchRequest, search


def test_search_falls_back_to_db_chunks_when_qdrant_fails(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", testing_session_local)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    try:
        user = User(
            email="search@example.com",
            hashed_password="x",
            full_name="Search User",
            role=UserRole.employee,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        document = Document(
            filename="sample.txt",
            original_filename="sample.txt",
            file_path="uploads/sample.txt",
            file_type="txt",
            file_size=10,
            department="hr",
            access_level=AccessLevel.public,
            status="chunked",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        chunk = Chunk(
            document_id=document.id,
            chunk_index=0,
            text="This chunk contains the uploaded document contents.",
            is_embedded=False,
        )
        db.add(chunk)
        db.commit()

        monkeypatch.setattr(search_v1, "_get_qdrant", lambda: (_ for _ in ()).throw(RuntimeError("qdrant down")))
        monkeypatch.setattr(search_v1, "embed_query", lambda query: [0.1, 0.2])
        monkeypatch.setattr(search_v1, "build_answer", lambda query, chunks: "fallback answer")

        response = search(
            SearchRequest(query="uploaded document", limit=5),
            current_user=user,
            db=db,
        )

        assert response["has_answer"] is True
        assert len(response["results"]) == 1
        assert "uploaded document contents" in response["results"][0]["text_preview"]
        assert response["answer"] == "fallback answer"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
