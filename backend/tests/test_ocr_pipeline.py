import os
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Document, DocumentStatus, AccessLevel
from app.services.extractor import extract_text
from app.services.chunker import chunk_document
from app.services.embedder import embed_document, get_qdrant_stats


class OCRPipelineTests(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for test session state
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_ocr_extraction_chunking_and_embedding(self):
        """Test full pipeline: Extract (OCR) -> Chunk -> Embed on a scanned document."""
        # Find a scanned PDF file from the user's uploads folder
        scanned_pdf_dir = Path(r"C:\Maantic\uploads")
        if not scanned_pdf_dir.exists():
            scanned_pdf_dir = Path(__file__).parent.parent / "uploads"

        scanned_files = list(scanned_pdf_dir.glob("*Scanned*.pdf")) + list(scanned_pdf_dir.glob("*Invoice*.pdf"))
        if not scanned_files:
            self.skipTest("No scanned PDF files found to test OCR extraction.")

        target_file = scanned_files[0]
        print(f"\nTesting OCR pipeline with: {target_file.name}")

        # 1. Create a Document record in the DB
        doc = Document(
            filename=target_file.name,
            original_filename=target_file.name,
            file_path=str(target_file),
            file_type="pdf",
            file_size=target_file.stat().st_size,
            department="HR",
            access_level=AccessLevel.public,
            status=DocumentStatus.pending,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # 2. Extract text (should trigger local OCR fallback since scanned PDF has no native text)
        doc.status = DocumentStatus.extracting
        self.db.commit()

        text, pages = extract_text(doc.file_path, doc.file_type)
        self.assertIsNotNone(text)
        self.assertTrue(len(text.strip()) > 0, "OCR produced empty text.")
        print(f"  Successfully extracted {len(text)} characters of text from {pages} pages.")

        doc.extracted_text = text
        doc.page_count = pages
        doc.status = DocumentStatus.extracted
        self.db.commit()

        # 3. Chunk the extracted text
        chunk_document(doc, self.db)
        self.db.refresh(doc)

        self.assertEqual(doc.status, DocumentStatus.chunked)
        self.assertTrue(len(doc.chunks) > 0, "No chunks were created.")
        print(f"  Successfully split document into {len(doc.chunks)} chunks.")

        # 4. Embed chunks into Qdrant vector database
        doc.status = DocumentStatus.embedding
        self.db.commit()

        stats_before = get_qdrant_stats()
        points_before = stats_before.get("points_count", 0) or 0

        result = embed_document(doc, self.db)
        self.db.refresh(doc)

        self.assertEqual(doc.status, DocumentStatus.embedded)
        self.assertTrue(result.get("embedded", 0) > 0, "No chunks were embedded.")
        print(f"  Successfully embedded {result['embedded']} chunks into Qdrant collection.")

        stats_after = get_qdrant_stats()
        points_after = stats_after.get("points_count", 0) or 0
        print(f"  Qdrant points count changed: {points_before} -> {points_after}")


if __name__ == "__main__":
    unittest.main()
