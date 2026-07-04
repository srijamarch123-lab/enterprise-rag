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

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, Timeout, APIError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def stream_chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024):
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in response:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content", "")
                if content:
                    yield content
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
            logger.exception("Unexpected error during streamed chat completion.")
            raise


def build_fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Create a simple answer from retrieved chunks when LLM calls are unavailable."""
    if not chunks:
        return "I don't know based on the provided documents."

    relevant = []
    for chunk in chunks[:3]:
        text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        if text:
            relevant.append(text)

    if not relevant:
        return "I don't know based on the provided documents."

    excerpt = " ".join(relevant[:2])
    excerpt = " ".join(excerpt.split())
    if len(excerpt) > 900:
        excerpt = excerpt[:900] + "..."

    return (
        f"Based on the available document context, the relevant information is: {excerpt}\n\n"
        "Sources: " + ", ".join(
            str(chunk.get("document_id") or chunk.get("chunk_id") or "document")
            for chunk in chunks[:3]
        )
    )


def build_chat_prompt(
    query: str,
    chunks: list[dict[str, Any]],
    history_messages: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, str]]:
    """Build a chat completion prompt from retrieved chunks and recent conversation history."""
    if not chunks:
        return []

    context_text = assemble_context(chunks)
    if not context_text:
        return []

    history_block = ""
    if history_messages:
        history_lines: list[str] = []
        for entry in history_messages[-6:]:
            role = (entry.get("role") or "user").strip().lower()
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            history_lines.append(f"{role.capitalize()}: {content}")
        if history_lines:
            history_block = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Answer the user's question using only the following document context. "
                "Do not invent facts or use any information outside the context. "
                "If the answer cannot be determined from the context, say: 'I don't know based on the provided documents.'\n\n"
                f"{history_block}"
                f"Question: {query}\n\n"
                "Context:\n"
                f"{context_text}"
            ),
        },
    ]


def build_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Build the answer text from query and retrieved chunk context."""
    if not chunks:
        return "I don't know based on the provided documents."

    messages = build_chat_prompt(query, chunks)
    if not messages:
        return build_fallback_answer(query, chunks)

    try:
        llm = LLMService()
        return llm.chat_completion(messages=messages, max_tokens=900)
    except Exception as exc:
        logger.warning("Falling back to local answer generation: %s", exc)
        return build_fallback_answer(query, chunks)
