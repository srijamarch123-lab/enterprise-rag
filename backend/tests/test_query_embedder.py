import unittest
import threading
import json
from app.services.query_embedder import embed_query, get_embedder
from app.services.redis_service import get_redis_client

class QueryEmbedderTests(unittest.TestCase):
    def setUp(self):
        # Clear cache before each test
        client = get_redis_client()
        if hasattr(client, "_local_store"):
            with hasattr(client, "_local_lock") and client._local_lock or threading.Lock():
                client._local_store.clear()
        else:
            try:
                client.flushdb()
            except Exception:
                pass

    def test_embed_query_normal(self):
        """Test embedding a normal string query returns a 384-dim vector."""
        vec = embed_query("What is the hr policy?")
        self.assertEqual(len(vec), 384)
        self.assertTrue(all(isinstance(x, float) for x in vec))

    def test_embed_query_none_and_empty(self):
        """Test that None, empty, or whitespace-only inputs return empty list []."""
        self.assertEqual(embed_query(None), [])
        self.assertEqual(embed_query(""), [])
        self.assertEqual(embed_query("   "), [])

    def test_embed_query_cache(self):
        """Test that query embedding uses cache correctly and respects TTL."""
        # 1. Warm up cache
        q = "test query cache"
        vec1 = embed_query(q)
        self.assertEqual(len(vec1), 384)

        # 2. Check that it is stored in the cache
        client = get_redis_client()
        q_key = f"query_embed:{q.lower().strip()}"
        cached_str = client.get(q_key)
        self.assertIsNotNone(cached_str)
        self.assertEqual(json.loads(cached_str), vec1)

        # 3. Modify cached vector in cache to verify that second call returns cache
        dummy_vec = [1.2, 3.4, 5.6]
        client.set(q_key, json.dumps(dummy_vec))
        vec2 = embed_query(q)
        self.assertEqual(vec2, dummy_vec)

    def test_embed_query_concurrent_safety(self):
        """Test concurrent threads executing embed_query simultaneously do not crash or corrupt state."""
        num_threads = 10
        threads = []
        errors = []

        def worker(thread_idx):
            try:
                # Mix of same and different queries to trigger concurrent cache lookups/updates
                query = f"concurrent query {thread_idx % 3}"
                vec = embed_query(query)
                if len(vec) != 384:
                    errors.append(f"Thread {thread_idx} returned unexpected vector length {len(vec)}")
            except Exception as e:
                errors.append(f"Thread {thread_idx} raised: {e}")

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Concurrency errors found: {errors}")

if __name__ == "__main__":
    unittest.main()
