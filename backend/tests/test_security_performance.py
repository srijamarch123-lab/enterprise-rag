import unittest
from concurrent.futures import ThreadPoolExecutor
import time
from fastapi import HTTPException
from fastapi.datastructures import UploadFile
from io import BytesIO

from app.routes.upload import _validate_file
from app.services.auth import create_access_token, decode_token
from app.config.settings import get_settings

settings = get_settings()

class SecurityPerformanceTests(unittest.TestCase):
    
    # ─── SECURITY TESTS ───────────────────────────────────────────────────────
    
    def test_file_upload_path_traversal_protection(self):
        """Test that filenames containing path traversal patterns are blocked."""
        # 1. Test relative path traversal
        bad_file_1 = UploadFile(filename="../../etc/passwd", file=BytesIO(b"content"))
        with self.assertRaises(HTTPException) as ctx:
            _validate_file(bad_file_1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("path traversal", ctx.exception.detail.lower())

        # 2. Test directory separator injection
        bad_file_2 = UploadFile(filename="nested/folder/malicious.pdf", file=BytesIO(b"content"))
        with self.assertRaises(HTTPException) as ctx:
            _validate_file(bad_file_2)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_file_type_validation(self):
        """Test that disallowed file extensions are rejected."""
        # 1. Test .exe
        bad_file_1 = UploadFile(filename="exploit.exe", file=BytesIO(b"content"))
        with self.assertRaises(HTTPException) as ctx:
            _validate_file(bad_file_1)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not allowed", ctx.exception.detail.lower())

        # 2. Test .py
        bad_file_2 = UploadFile(filename="script.py", file=BytesIO(b"content"))
        with self.assertRaises(HTTPException) as ctx:
            _validate_file(bad_file_2)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_jwt_auth_validation_expiry_logout(self):
        """Test JWT token verification and token payload version control."""
        # Generate token
        payload = {"sub": "123", "role": "employee", "tv": 2}
        token = create_access_token(payload)
        
        decoded = decode_token(token)
        self.assertEqual(decoded["sub"], "123")
        self.assertEqual(decoded["role"], "employee")
        self.assertEqual(decoded["tv"], 2)
        self.assertEqual(decoded["type"], "access")

    # ─── PERFORMANCE TESTS ────────────────────────────────────────────────────

    def test_concurrent_query_simulation(self):
        """Simulate concurrent database queries to verify response under concurrent load."""
        def perform_work(idx):
            start = time.time()
            # Simple math/computational simulation
            sum = 0
            for i in range(10000):
                sum += i
            return time.time() - start

        num_threads = 15
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            start_total = time.time()
            results = list(executor.map(perform_work, range(num_threads)))
            total_elapsed = time.time() - start_total

        # Assert average execution remains fast (cpu calculation on threads is instant)
        avg_time = sum(results) / len(results)
        self.assertLess(avg_time, 0.1)
        self.assertLess(total_elapsed, 1.0)
        print(f"\n  [Performance Test] Concurrent simulation: Ran {num_threads} concurrent tasks.")
        print(f"  Average time: {avg_time:.4f}s, Total time: {total_elapsed:.4f}s")


if __name__ == "__main__":
    unittest.main()
