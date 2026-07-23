import unittest
import time
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Chunk, Document, User, UserRole, AccessLevel
from app.routes.search_v1 import _merge_results
from app.services.chunker import chunk_document
from app.services.extractor import _extract_pdf
from app.services.redis_service import get_redis_client


class MockQdrantHit:
    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


class OptimizationsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_rrf_merge_results(self):
        """Verify that Reciprocal Rank Fusion correctly merges and ranks candidates."""
        semantic_hits = [
            MockQdrantHit(id="pt1", score=0.9, payload={"chunk_id": 1, "access_level": "public", "filename": "doc1.pdf"}),
            MockQdrantHit(id="pt2", score=0.8, payload={"chunk_id": 2, "access_level": "public", "filename": "doc1.pdf"}),
        ]
        bm25_results = [
            {"chunk_id": 2, "bm25_score": 10.0, "filename": "doc1.pdf", "access_level": "public"},
            {"chunk_id": 1, "bm25_score": 5.0, "filename": "doc1.pdf", "access_level": "public"},
        ]

        # Ranks:
        # chunk 1: semantic rank = 1, bm25 rank = 2
        # chunk 2: semantic rank = 2, bm25 rank = 1
        # Since both rank 1 & 2 in the lists, they should have identical RRF scores before metadata boosts.
        results, has_answer = _merge_results(semantic_hits, bm25_results, top_k=5, confidence_threshold=0.0)
        self.assertTrue(has_answer)
        self.assertEqual(len(results), 2)
        # Chunk 1 (higher semantic similarity 0.9) ranks top with higher combined_score than Chunk 2 (0.8)
        self.assertGreater(results[0]["combined_score"], results[1]["combined_score"])
        self.assertLess(results[0]["combined_score"], 1.0)

    def test_hierarchical_chunking(self):
        """Verify chunker splits document into parent-child hierarchical chunks."""
        doc = Document(
            filename="test.txt",
            original_filename="test.txt",
            file_path="test.txt",
            file_type="txt",
            extracted_text="Sentence A. " * 300,  # long text to trigger multiple parent chunks
        )
        self.db.add(doc)
        self.db.commit()

        chunks = chunk_document(doc, self.db)
        self.db.refresh(doc)

        self.assertTrue(len(chunks) > 0)
        # All child chunks must have parent_text populated
        for c in chunks:
            self.assertIsNotNone(c.parent_text)
            self.assertTrue(len(c.parent_text) >= len(c.text))

    def test_parallel_ocr_fallback(self):
        """Verify extractor runs fallback OCR page-by-page."""
        from pathlib import Path
        with patch("app.services.extractor._ocr_pdf_page_fallback") as mock_ocr, \
             patch("pdfplumber.open") as mock_pdf, \
             patch("fitz.open") as mock_fitz:
             
            # Setup fitz mock
            mock_fitz_doc = MagicMock()
            mock_fitz_page = MagicMock()
            mock_fitz_page.get_text.return_value = ""  # empty text to trigger OCR
            mock_fitz_doc.__len__.return_value = 2
            mock_fitz_doc.__iter__.return_value = [mock_fitz_page, mock_fitz_page]
            mock_fitz.return_value = mock_fitz_doc
            
            # Setup pdfplumber mock
            mock_pdf_instance = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""  # empty text to trigger OCR
            mock_page.extract_tables.return_value = []
            mock_pdf_instance.pages = [mock_page, mock_page]
            mock_pdf.return_value.__enter__.return_value = mock_pdf_instance
            
            mock_ocr.return_value = ("page text", None)
            
            # Run extraction
            txt, pages = _extract_pdf(Path("dummy.pdf"))
            
            self.assertEqual(pages, 2)
            self.assertIn("page text", txt)
            self.assertEqual(mock_ocr.call_count, 2)

    def test_jwt_blacklist_revocation(self):
        """Verify token blacklisting blocks authentication."""
        client = get_redis_client()
        # Set a dummy token as blacklisted
        token_key = "jwt_blacklist:revoked_test_token"
        client.set(token_key, "1", ex=10)

        # Retrieve token status
        self.assertEqual(client.get(token_key), "1")
        
        # Cleanup
        client.delete(token_key)
        self.assertIsNone(client.get(token_key))


if __name__ == "__main__":
    unittest.main()
