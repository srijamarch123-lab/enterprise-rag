import unittest
import unittest.mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Document, User, UserRole
from app.services.versioning import handle_document_versioning
from app.routes.search_v1 import _get_visible_doc_ids_for_role

class AdvancedFeaturesTests(unittest.TestCase):
    def setUp(self):
        # Create clean in-memory sqlite db
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_document_versioning_and_archiving(self):
        """Verify that handle_document_versioning archives old documents and increments versions."""
        # 1. Create initial active document
        doc1 = Document(
            filename="saved_v1.txt",
            original_filename="policy.txt",
            file_path="path/to/v1",
            file_type="txt",
            file_size=100,
            department="HR",
            source="manual",
            is_active=True,
            version=1
        )
        self.db.add(doc1)
        self.db.commit()

        # 2. Call handle_document_versioning for the same filename
        new_version = handle_document_versioning(
            db=self.db,
            original_filename="policy.txt",
            owner_user_id=None,
            department="HR"
        )

        # 3. Retrieve documents and assert
        self.db.refresh(doc1)
        self.assertEqual(doc1.is_active, False)
        self.assertEqual(new_version, 2)

    def test_get_visible_doc_ids_filters_active(self):
        """Verify that _get_visible_doc_ids_for_role only returns active documents."""
        # 1. Create one active and one inactive document
        doc_active = Document(
            filename="active.txt",
            original_filename="active.txt",
            file_path="path/to/active",
            file_type="txt",
            file_size=100,
            department="HR",
            source="manual",
            is_active=True,
            version=1
        )
        doc_inactive = Document(
            filename="inactive.txt",
            original_filename="inactive.txt",
            file_path="path/to/inactive",
            file_type="txt",
            file_size=100,
            department="HR",
            source="manual",
            is_active=False,
            version=1
        )
        self.db.add(doc_active)
        self.db.add(doc_inactive)
        self.db.commit()

        # 2. Retrieve visible doc IDs for role "admin"
        visible_ids = _get_visible_doc_ids_for_role(role="admin", db=self.db)
        
        # 3. Assert only active document is present
        self.assertIn(doc_active.id, visible_ids)
        self.assertNotIn(doc_inactive.id, visible_ids)

    @unittest.mock.patch("app.services.process_all.extract_text")
    @unittest.mock.patch("app.services.process_all.ensure_file_exists")
    @unittest.mock.patch("app.services.process_all.chunk_document")
    @unittest.mock.patch("app.services.process_all.embed_document")
    def test_self_healing_unknown_file_type(self, mock_embed, mock_chunk, mock_ensure_exists, mock_extract):
        """Verify that process_single_document_by_id self-heals unknown file types from their original filename."""
        mock_extract.return_value = ("some text content", 1)
        
        doc = Document(
            filename="temp.unknown",
            original_filename="Enterprise_RAG_Gantt_v4 (1).xlsx",
            file_path="temp.unknown",
            file_type="unknown",
            file_size=100,
            department="HR",
            source="drive",
            is_active=True,
            version=1
        )
        self.db.add(doc)
        self.db.commit()

        # Patch SessionLocal to use our in-memory DB and prevent close() from expiring the session
        self.db.close = lambda: None
        with unittest.mock.patch("app.database.SessionLocal", return_value=self.db):
            from app.services.process_all import process_single_document_by_id
            process_single_document_by_id(doc.id)
        
        # Query again with a new session to ensure state is fetched cleanly
        new_db = self.SessionLocal()
        try:
            doc = new_db.query(Document).filter(Document.id == doc.id).first()
            self.assertEqual(doc.file_type, "xlsx")
        finally:
            new_db.close()
