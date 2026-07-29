import unittest
import unittest.mock

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

    @unittest.mock.patch("app.services.llm_service.LLMService")
    def test_condense_query_calls_llm_with_history(self, mock_llm_class):
        import unittest.mock
        from app.services.llm_service import condense_query
        
        mock_llm_instance = mock_llm_class.return_value
        mock_llm_instance.chat_completion.return_value = "Standalone Query for Summarizing Onboarding Guide"
        
        history = [
            {"role": "user", "content": "What is this document about?"},
            {"role": "assistant", "content": "It is an onboarding guide."},
        ]
        
        result = condense_query("Summarize it", history)
        
        self.assertEqual(result, "Standalone Query for Summarizing Onboarding Guide")
        mock_llm_instance.chat_completion.assert_called_once()
        
        # Verify call arguments contain history and query
        call_args = mock_llm_instance.chat_completion.call_args[1]["messages"][0]["content"]
        self.assertIn("User: What is this document about?", call_args)
        self.assertIn("Assistant: It is an onboarding guide.", call_args)
        self.assertIn("Follow-up Question: Summarize it", call_args)


if __name__ == "__main__":
    unittest.main()

