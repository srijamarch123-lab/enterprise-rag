import unittest
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
