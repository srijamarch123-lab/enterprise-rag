import logging
from typing import Any, Iterable, List, Optional

import openai
import tiktoken
from openai import APIConnectionError, APIError, RateLimitError, Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
openai.api_key = settings.openai_api_key

ENCODING = tiktoken.get_encoding("cl100k_base")

SYSTEM_PROMPT = """You are a helpful assistant that answers user questions using only the provided document context.
Do not hallucinate or use any information that is not explicitly contained in the context.
If the answer cannot be found in the context, respond with: "I don't know based on the provided documents."
Provide the response in Markdown format, using headings, bullets, and tables when appropriate.
At the end of the answer, include a Sources section that cites the documents and pages used.
"""

MAX_CONTEXT_TOKENS = 3000


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def assemble_context(chunks: list[dict[str, Any]], token_limit: int = MAX_CONTEXT_TOKENS) -> str:
    """Deduplicate and assemble the top chunks into a token-limited context block."""
    seen_texts: set[str] = set()
    output_sections: list[str] = []
    total_tokens = 0

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        normalized_text = " ".join(text.split())
        if normalized_text in seen_texts:
            continue

        source = chunk.get("filename") or "unknown source"
        document_id = chunk.get("document_id")
        page_number = chunk.get("page_number")
        chunk_index = chunk.get("chunk_index")

        section = (
            f"Source: {source} | Document ID: {document_id} | Page: {page_number} | Chunk: {chunk_index}\n"
            f"{text}\n"
        )
        section_tokens = count_tokens(section)
        if total_tokens + section_tokens > token_limit:
            break

        output_sections.append(section)
        seen_texts.add(normalized_text)
        total_tokens += section_tokens

    return "\n".join(output_sections).strip()


class LLMService:
    def __init__(self, model: str = "gpt-4.1", temperature: float = 0.0, max_retries: int = 3):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required for LLMService.")
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, Timeout, APIError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024) -> str:
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise ValueError("OpenAI returned no choices.")
            message = choices[0].get("message") or {}
            return message.get("content", "").strip()
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit encountered, retrying: %s", exc)
            raise
        except (APIConnectionError, Timeout) as exc:
            logger.warning("OpenAI connection error, retrying: %s", exc)
            raise
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise
        except Exception as exc:
            logger.exception("Unexpected error calling OpenAI chat completion.")
            raise


def build_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Build the answer text from query and retrieved chunk context."""
    if not chunks:
        return ""

    context_text = assemble_context(chunks)
    if not context_text:
        return ""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Answer the user's question using only the following document context. "
                "Do not invent facts or use any information outside the context. "
                "If the answer cannot be determined from the context, say: 'I don't know based on the provided documents.'\n\n"
                f"Question: {query}\n\n"
                "Context:\n"
                f"{context_text}"
            ),
        },
    ]

    llm = LLMService()
    return llm.chat_completion(messages=messages, max_tokens=900)
