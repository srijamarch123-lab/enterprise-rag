import unittest

from app.services.llm_service import build_chat_prompt


class LLMServiceTests(unittest.TestCase):
    def test_build_chat_prompt_includes_history_and_context(self):
        chunks = [
            {
                "text": "The onboarding guide explains the policy.",
                "filename": "guide.pdf",
                "document_id": 1,
                "page_number": 2,
                "chunk_index": 0,
            }
        ]
        history = [
            {"role": "user", "content": "What is this document about?"},
            {"role": "assistant", "content": "It is an onboarding guide."},
        ]

        messages = build_chat_prompt("Summarize it", chunks, history_messages=history)

        self.assertTrue(messages)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Summarize it", messages[1]["content"])
        self.assertIn("Conversation history", messages[1]["content"])
        self.assertIn("User: What is this document about?", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
