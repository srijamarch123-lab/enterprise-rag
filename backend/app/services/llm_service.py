import logging
import os
from typing import Any, Iterable, List, Optional
import tiktoken
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ENCODING = tiktoken.get_encoding("cl100k_base")

SYSTEM_PROMPT = """You are a helpful enterprise document assistant. Answer the user's question using only the provided document context.
Do not hallucinate or use any information not explicitly in the context.
If the answer cannot be found, respond with: "I don't know based on the provided documents."
Format your response clearly using bullet points and short paragraphs.
Keep the answer concise and directly relevant to the question asked.
At the end, add a brief "Sources:" line listing only the document names used."""

MAX_CONTEXT_TOKENS = 3000


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def assemble_context(chunks: list[dict[str, Any]], token_limit: int = MAX_CONTEXT_TOKENS) -> str:
    sorted_chunks = sorted(
        chunks,
        key=lambda x: x.get("combined_score") or x.get("score") or x.get("bm25_score") or 0.0,
        reverse=True,
    )
    seen_texts: set[str] = set()
    output_sections: list[str] = []
    total_tokens = 0

    for chunk in sorted_chunks:
        text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        if not text:
            continue
        normalized_text = " ".join(text.split())
        if normalized_text in seen_texts:
            continue
        source = chunk.get("filename") or "unknown source"
        page_number = chunk.get("page_number")
        section = f"Source: {source}" + (f" | Page: {page_number}" if page_number else "") + f"\n{text}\n"
        section_tokens = count_tokens(section)
        if total_tokens + section_tokens > token_limit:
            break
        output_sections.append(section)
        seen_texts.add(normalized_text)
        total_tokens += section_tokens

    return "\n".join(output_sections).strip()


def _get_groq_client():
    groq_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "groq_api_key", None)
    if not groq_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=groq_key)
    except ImportError:
        logger.warning("groq package not installed. Run: pip install groq")
        return None


def _groq_chat(messages: list[dict], max_tokens: int = 900) -> str:
    client = _get_groq_client()
    if not client:
        raise RuntimeError("Groq client not available")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _groq_stream(messages: list[dict], max_tokens: int = 900):
    client = _get_groq_client()
    if not client:
        raise RuntimeError("Groq client not available")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in response:
        content = chunk.choices[0].delta.content if chunk.choices else None
        if content:
            yield content


class LLMService:
    def __init__(self, model: str = None, temperature: float = 0.0, max_retries: int = 3):
        self.model = model or "gpt-4o-mini"
        self.temperature = temperature
        self.max_retries = max_retries
        self._openai_client = None
        if settings.openai_api_key:
            try:
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                pass

    def chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024) -> str:
        # Try OpenAI first
        if self._openai_client:
            try:
                response = self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except RateLimitError as e:
                if "insufficient_quota" in str(e):
                    logger.warning("OpenAI quota exhausted, falling back to Groq")
                else:
                    logger.warning("OpenAI rate limit, falling back to Groq: %s", e)
            except Exception as e:
                logger.warning("OpenAI failed, falling back to Groq: %s", e)

        # Fallback to Groq
        try:
            return _groq_chat(messages, max_tokens=max_tokens)
        except Exception as e:
            logger.error("Groq also failed: %s", e)
            raise

    def stream_chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024):
        # Try OpenAI streaming first
        if self._openai_client:
            try:
                response = self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                for chunk in response:
                    content = chunk.choices[0].delta.content if chunk.choices else None
                    if content:
                        yield content
                return
            except RateLimitError as e:
                if "insufficient_quota" in str(e):
                    logger.warning("OpenAI quota exhausted, falling back to Groq stream")
                else:
                    logger.warning("OpenAI rate limit, falling back to Groq stream: %s", e)
            except Exception as e:
                logger.warning("OpenAI stream failed, falling back to Groq: %s", e)

        # Fallback to Groq streaming
        try:
            yield from _groq_stream(messages, max_tokens=max_tokens)
        except Exception as e:
            logger.error("Groq stream also failed: %s", e)
            raise


def generate_suggested_questions(query: str, answer: str, context: str) -> list[str]:
    if not answer or answer == "I don't know based on the provided documents.":
        return [
            "What documents are available?",
            "Summarize the main policies",
            "Who has access to internal documents?"
        ]
    prompt = (
        "Based on the following user query, generated answer, and context, generate 3 short relevant follow-up questions.\n"
        "Return ONLY the questions, one per line, no numbering or extra text.\n\n"
        f"Query: {query}\n\nAnswer: {answer}\n\nContext:\n{context}\n\nSuggested Questions:"
    )
    try:
        llm = LLMService(temperature=0.7)
        messages = [
            {"role": "system", "content": "You generate short follow-up questions."},
            {"role": "user", "content": prompt}
        ]
        res = llm.chat_completion(messages=messages, max_tokens=150)
        import re
        questions = [re.sub(r'^\d+[\.\)]\s*', '', q.strip().strip("-*\"")).strip() for q in res.split("\n") if q.strip()]
        cleaned = [q for q in questions if len(q) > 5][:5]
        if len(cleaned) < 3:
            cleaned = [f"Tell me more about {query}", "Show the key points", "What other documents relate to this?"]
        return cleaned
    except Exception as exc:
        logger.warning("Failed to generate suggested questions: %s", exc)
        return ["Can you explain more?", "Show the key points", "What other documents relate to this?"]


def build_fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "I don't know based on the provided documents."
    relevant = []
    source_ids = []
    for chunk in chunks[:3]:
        text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        if text:
            relevant.append(text)
            doc_id = chunk.get("document_id") or chunk.get("doc_id") or chunk.get("id")
            if doc_id is not None:
                doc_str = str(doc_id)
                if doc_str not in source_ids:
                    source_ids.append(doc_str)
    if not relevant:
        return "I don't know based on the provided documents."
    excerpt = " ".join(relevant[:2])
    excerpt = " ".join(excerpt.split())
    if len(excerpt) > 600:
        excerpt = excerpt[:600] + "..."
    sources_part = ""
    if source_ids:
        sources_part = f"\n\nSources: {', '.join(source_ids)}"
    return f"Based on the available documents:\n\n{excerpt}{sources_part}"


def build_chat_prompt(
    query: str,
    chunks: list[dict[str, Any]],
    history_messages: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, str]]:
    if not chunks:
        return []
    context_text = assemble_context(chunks)
    if not context_text:
        return []
    history_block = ""
    if history_messages:
        history_lines = []
        for entry in history_messages[-6:]:
            role = (entry.get("role") or "user").strip().lower()
            content = (entry.get("content") or "").strip()
            if content:
                history_lines.append(f"{role.capitalize()}: {content}")
        if history_lines:
            history_block = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{history_block}"
                f"Question: {query}\n\n"
                f"Context:\n{context_text}"
            ),
        },
    ]


def build_answer(query: str, chunks: list[dict[str, Any]]) -> str:
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
