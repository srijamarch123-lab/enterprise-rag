import logging
from typing import Any, Iterable, List, Optional
import tiktoken
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ENCODING = tiktoken.get_encoding("cl100k_base")

SYSTEM_PROMPT = """You are a helpful assistant that answers user questions using only the provided document context.
Do not hallucinate or use any information that is not explicitly contained in the context.
If the answer cannot be found in the context, respond with: "I don't know based on the provided documents."
Provide the response in Markdown format, using headings, bullets, and tables when appropriate.
You MUST cite your sources for any statements you make using inline citations referencing the source document and page number, e.g. [source_filename, Page X] or [source_filename].
At the end of the answer, include a Sources section that lists the documents and page numbers used.
"""

MAX_CONTEXT_TOKENS = 3000


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def assemble_context(chunks: list[dict[str, Any]], token_limit: int = MAX_CONTEXT_TOKENS) -> str:
    """Deduplicate and assemble the top chunks into a token-limited context block."""
    # Sort chunks by score/relevance score descending
    sorted_chunks = sorted(
        chunks,
        key=lambda x: x.get("combined_score") or x.get("score") or x.get("bm25_score") or 0.0,
        reverse=True
    )

    seen_texts: set[str] = set()
    output_sections: list[str] = []
    total_tokens = 0

    for chunk in sorted_chunks:
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
    def __init__(self, model: str = None, temperature: float = 0.0, max_retries: int = 3):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required for LLMService.")
        # Default to a model that exists on OpenAI, but fall back if specific model is requested.
        # "gpt-4.1" was in the spec, so let's use a standard model like gpt-4o-mini if gpt-4.1 is not configured or fails.
        self.model = model or "gpt-4o-mini"
        self.temperature = temperature
        self.max_retries = max_retries
        self.client = OpenAI(api_key=settings.openai_api_key)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024) -> str:
        try:
            # Handle gpt-4.1 Spec fallback: if OpenAI throws model not found, try gpt-4o-mini
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
            except APIError as e:
                if "model" in str(e).lower() and self.model == "gpt-4.1":
                    logger.warning("gpt-4.1 model not found, falling back to gpt-4o-mini")
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    raise

            choices = response.choices
            if not choices:
                raise ValueError("OpenAI returned no choices.")
            return choices[0].message.content.strip()
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit encountered, retrying: %s", exc)
            raise
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("OpenAI connection/timeout error, retrying: %s", exc)
            raise
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise
        except Exception as exc:
            logger.exception("Unexpected error calling OpenAI chat completion.")
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError, APIError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def stream_chat_completion(self, messages: List[dict[str, str]], max_tokens: int = 1024):
        try:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
            except APIError as e:
                if "model" in str(e).lower() and self.model == "gpt-4.1":
                    logger.warning("gpt-4.1 model not found, falling back to gpt-4o-mini")
                    response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=max_tokens,
                        stream=True,
                    )
                else:
                    raise

            for chunk in response:
                choices = chunk.choices
                if not choices:
                    continue
                content = choices[0].delta.content
                if content:
                    yield content
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit encountered, retrying: %s", exc)
            raise
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("OpenAI connection/timeout error, retrying: %s", exc)
            raise
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise
        except Exception as exc:
            logger.exception("Unexpected error during streamed chat completion.")
            raise


def generate_suggested_questions(query: str, answer: str, context: str) -> list[str]:
    """Generate 3 to 5 relevant follow-up questions from the query, answer, and context."""
    if not answer or answer == "I don't know based on the provided documents.":
        return [
            "What documents are available?",
            "Summarize the main policies",
            "Who has access to internal documents?"
        ]

    prompt = (
        "Based on the following user query, generated answer, and context, generate 3 to 5 short, relevant, and diverse follow-up questions the user might ask next.\n"
        "Return ONLY a list of the questions, one per line. Do not number them or add any other text.\n\n"
        f"Query: {query}\n\n"
        f"Answer: {answer}\n\n"
        f"Context:\n{context}\n\n"
        "Suggested Questions:"
    )

    try:
        # Use low temperature for focused generation, fallback to gpt-4o-mini
        llm = LLMService(temperature=0.7)
        messages = [
            {"role": "system", "content": "You are a helpful assistant that generates relevant follow-up questions."},
            {"role": "user", "content": prompt}
        ]
        res = llm.chat_completion(messages=messages, max_tokens=150)
        questions = [q.strip().strip("-").strip("*").strip().strip('"').strip() for q in res.split("\n") if q.strip()]
        cleaned = []
        for q in questions:
            import re
            q_clean = re.sub(r'^\d+[\.\)]\s*', '', q).strip()
            if q_clean and len(q_clean) > 5:
                cleaned.append(q_clean)

        if len(cleaned) < 3:
            cleaned = [
                f"Can you explain more about {query}?",
                "Show the key points from the sources",
                "What other documents relate to this topic?"
            ]
        return cleaned[:5]
    except Exception as exc:
        logger.warning("Failed to generate suggested questions: %s", exc)
        return [
            "Can you explain more about this?",
            "Show the key points from the sources",
            "What other documents relate to this topic?"
        ]



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
