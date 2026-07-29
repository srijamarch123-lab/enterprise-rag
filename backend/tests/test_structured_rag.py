import unittest
from unittest.mock import patch, MagicMock
import json
import math
from pathlib import Path

from app.models import Document, Chunk, SemanticCache, User
from app.services.chunker import chunk_document
from app.routes.search_v1 import search, SearchRequest

class StructuredRagTests(unittest.TestCase):

    def setUp(self):
        # Setup common mock database
        self.db = MagicMock()
        
        # Setup mock user
        self.user = User(
            id=1,
            email="test@maantic.com",
            role="user"
        )

    def test_structured_spreadsheet_chunking(self):
        """Test spreadsheet chunking formats sheets and rows into Markdown tables with header prefixes."""
        # Create a mock spreadsheet document
        doc = Document(
            id=42,
            file_path="dummy.xlsx",
            file_type="xlsx",
            status="extracted",
            extracted_text="header text"
        )
        
        # Mock extractor read_xlsx_file
        sheets_mock_data = {
            "SheetA": [
                ["ID", "Name", "Salary"],
                ["1", "Alice", "1000"],
                ["2", "Bob", "1500"]
            ]
        }
        
        with patch("app.services.extractor.read_xlsx_file", return_value=sheets_mock_data):
            chunks = chunk_document(doc, self.db)
            
            self.assertTrue(len(chunks) > 0)
            c = chunks[0]
            # Must contain Sheet name
            self.assertIn("Sheet: SheetA", c.text)
            # Must contain headers and rows formatted as Markdown tables
            self.assertIn("ID | Name | Salary", c.text)
            self.assertIn("Alice | 1000", c.text)
            self.assertIn("Bob | 1500", c.text)

    @patch("app.routes.search_v1.embed_query")
    @patch("app.routes.search_v1.build_answer")
    def test_semantic_cache_hit(self, mock_build_answer, mock_embed_query):
        """Test that query matching a cached entry above similarity threshold hits the cache directly."""
        mock_embed_query.return_value = [0.1, 0.2, 0.3]
        
        # Prepare cached entry with 1.0 similarity (identical embedding)
        cached_entry = SemanticCache(
            query="original query",
            embedding_json=json.dumps([0.1, 0.2, 0.3]),
            response_json=json.dumps({"answer": "Cached response payload", "results": []}),
            role="user"
        )
        
        # Mock database query
        self.db.query().filter().all.return_value = [cached_entry]
        
        req = SearchRequest(query="original query")
        res = search(req, current_user=self.user, db=self.db)
        
        # Should return cached payload instantly without calling LLM build_answer
        self.assertEqual(res["answer"], "Cached response payload")
        mock_build_answer.assert_not_called()

    @patch("app.routes.search_v1.embed_query")
    @patch("app.routes.search_v1._rerank_with_cross_encoder")
    @patch("app.routes.search_v1._merge_results")
    @patch("app.routes.search_v1.build_answer")
    def test_cross_encoder_rerank_is_called(self, mock_build_answer, mock_merge_results, mock_rerank, mock_embed):
        """Test that lightweight cross-encoder reranking is triggered on search results."""
        mock_embed.return_value = [0.1, 0.2, 0.3]
        
        # Mock hybrid merge
        merged_candidates = [{"text": "candidate 1", "combined_score": 0.4}, {"text": "candidate 2", "combined_score": 0.3}]
        mock_merge_results.return_value = (merged_candidates, True)
        
        # Mock rerank to return results
        mock_rerank.return_value = merged_candidates
        mock_build_answer.return_value = "Answer content"
        
        # Mock DB queries
        self.db.query().filter().all.return_value = []
        self.db.query().filter().first.return_value = None
        
        req = SearchRequest(query="What is remote policy?")
        search(req, current_user=self.user, db=self.db)
        
        # Rerank must be called on candidate list
        mock_rerank.assert_called_once()


if __name__ == "__main__":
    unittest.main()
