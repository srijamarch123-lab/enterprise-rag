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

SYSTEM_PROMPT = """You are an expert enterprise knowledge assistant.

RULES:
- Answer ONLY from the provided document context. Never use outside knowledge.
- If the answer is NOT found in the context, say ONLY: "I could not find this information in the available documents." Do NOT show any sources.
- ALWAYS structure your answer as bullet points using "- " prefix.
- Each bullet point must be a specific, concise fact extracted from the documents.
- After each bullet point, cite the source document in parentheses, e.g., (Source: Compliance & Legal Framework Document.pdf)
- Be precise — cite exact figures, dates, names, locations, and policies from the documents.
- Do NOT copy-paste entire paragraphs from the documents. Synthesize and summarize.
- Do NOT invent information. If a specific detail is not in the context, do not guess.
- At the end, add a line: "Sources: " followed by a comma-separated list of all referenced document names.
- If multiple documents support the same fact, cite all of them."""

MAX_CONTEXT_TOKENS = 6000


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
        text = (chunk.get("parent_text") or chunk.get("text") or chunk.get("text_preview") or "").strip()
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


def _groq_chat(messages: List[Any], max_tokens: int = 900) -> str:
    client = _get_groq_client()
    if not client:
        raise RuntimeError("Groq client not available")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,  # type: ignore
        temperature=0.0,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""


def _groq_stream(messages: List[Any], max_tokens: int = 900):
    client = _get_groq_client()
    if not client:
        raise RuntimeError("Groq client not available")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,  # type: ignore
        temperature=0.0,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in response:
        content = chunk.choices[0].delta.content if chunk.choices else None
        if content:
            yield content


class LLMService:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.0, max_retries: int = 3):
        self.model = model or "gpt-4o-mini"
        self.temperature = temperature
        self.max_retries = max_retries
        self._openai_client = None
        if settings.openai_api_key:
            try:
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                pass

    def chat_completion(self, messages: List[Any], max_tokens: int = 1024) -> str:
        # Try OpenAI first
        if self._openai_client:
            try:
                response = self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                return content.strip() if content else ""
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

    def stream_chat_completion(self, messages: List[Any], max_tokens: int = 1024):
        tokens_yielded = False
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
                        tokens_yielded = True
                        yield content
                return
            except Exception as e:
                if tokens_yielded:
                    logger.error("OpenAI stream failed mid-flight after tokens were yielded: %s", e)
                    return
                logger.warning("OpenAI stream failed before start, falling back to Groq: %s", e)

        # Fallback to Groq streaming if no tokens have been sent yet
        if not tokens_yielded:
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


def _is_raw_text_dump(answer: str, chunks: list[dict[str, Any]]) -> bool:
    """Detect if the LLM answer is just a raw copy of context text."""
    if not answer:
        return False
    answer_clean = " ".join(answer.split()).lower().strip()
    # Structural patterns that indicate raw dumps (no chunks needed)
    if answer_clean.startswith("based on the available documents:"):
        return True
    if "### source:" in answer_clean:
        return True
    if not chunks:
        return False
    # Check if answer is >80% identical to any single chunk
    for chunk in chunks:
        chunk_text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        if not chunk_text:
            continue
        chunk_clean = " ".join(chunk_text.split()).lower().strip()
        if len(chunk_clean) < 50:
            continue
        # Check overlap ratio
        if chunk_clean in answer_clean or answer_clean in chunk_clean:
            return True
        # Check if >80% of answer words appear verbatim in one chunk
        answer_words = set(answer_clean.split())
        chunk_words = set(chunk_clean.split())
        if answer_words and len(answer_words & chunk_words) / len(answer_words) > 0.80:
            return True
    return False


def build_fallback_answer(query: str, chunks: list[dict[str, Any]]) -> str:
    """Generate a structured bullet-point answer from chunks when LLM is unavailable.
    
    This is a LAST RESORT — it extracts the most relevant sentences from
    retrieved chunks and formats them as bullet points with source citations.
    It never dumps raw paragraphs.
    """
    if not chunks:
        return "I could not find this information in the available documents."
    
    query_lower = query.lower().strip()
    
    # 1. Handle "What documents are available?"
    if "other documents" in query_lower or "what documents" in query_lower or "list documents" in query_lower or "available documents" in query_lower:
        try:
            from app.database import SessionLocal
            from app.models import Document
            db = SessionLocal()
            try:
                docs = db.query(Document).all()
                doc_names = list(set([d.original_filename for d in docs if d.original_filename]))
                if doc_names:
                    doc_list_str = "\n".join([f"- {name}" for name in sorted(doc_names)])
                    sources_part = f"\n\nSources: {', '.join(doc_names[:5])}"
                    return f"The following documents are currently available:\n\n{doc_list_str}{sources_part}"
            finally:
                db.close()
        except Exception:
            pass

    # Extract sentences with source attribution
    query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]
    scored_sentences: list[tuple[int, str, str]] = []  # (score, sentence, source)
    source_names: list[str] = []

    for chunk in chunks:
        text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        fname = chunk.get("filename") or chunk.get("doc_name") or "Unknown"
        if fname and fname not in source_names:
            source_names.append(fname)
        if not text:
            continue

        # Split into sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 15 or len(sent) > 300:
                continue
            # Score by keyword overlap with query
            sent_lower = sent.lower()
            score = sum(1 for w in query_words if w in sent_lower)
            if score > 0:
                scored_sentences.append((score, sent, fname))

    if not scored_sentences:
        return "I could not find this information in the available documents."

    # Sort by relevance score descending, deduplicate
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    
    seen_sentences: set[str] = set()
    bullet_points: list[str] = []
    used_sources: list[str] = []
    
    for score, sent, fname in scored_sentences:
        # Deduplicate by normalized content
        normalized = " ".join(sent.lower().split())
        if normalized in seen_sentences:
            continue
        seen_sentences.add(normalized)
        
        # Format as bullet point with source citation
        bullet_points.append(f"- {sent} (Source: {fname})")
        if fname not in used_sources:
            used_sources.append(fname)
        
        if len(bullet_points) >= 6:
            break

    if not bullet_points:
        return "I could not find this information in the available documents."

    answer_body = "\n".join(bullet_points)
    sources_line = f"\n\nSources: {', '.join(used_sources)}"
    return f"{answer_body}{sources_line}"


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
        return "I could not find this information in the available documents."
    messages = build_chat_prompt(query, chunks)
    if not messages:
        return build_fallback_answer(query, chunks)
    try:
        llm = LLMService()
        answer = llm.chat_completion(messages=messages, max_tokens=900)
        # Validate: if the LLM just dumped raw text, regenerate with fallback
        if _is_raw_text_dump(answer, chunks):
            logger.warning("LLM returned raw text dump, using structured fallback")
            return build_fallback_answer(query, chunks)
        return answer
    except Exception as exc:
        logger.warning("Falling back to local answer generation: %s", exc)
        return build_fallback_answer(query, chunks)


def build_answer_stream(query: str, chunks: list[dict[str, Any]]):
    if not chunks:
        yield "I could not find this information in the available documents."
        return
    messages = build_chat_prompt(query, chunks)
    if not messages:
        yield build_fallback_answer(query, chunks)
        return
    try:
        llm = LLMService()
        collected_tokens: list[str] = []
        for token in llm.stream_chat_completion(messages=messages, max_tokens=900):
            collected_tokens.append(token)
            yield token
        # Post-stream validation: if the full answer is a raw dump, we can't undo
        # the stream but log it for monitoring
        full_answer = "".join(collected_tokens).strip()
        if _is_raw_text_dump(full_answer, chunks):
            logger.warning("Streamed answer was a raw text dump — consider prompt tuning")
    except Exception as exc:
        logger.warning("Streaming fell back to local answer generation: %s", exc)
        yield build_fallback_answer(query, chunks)


def parse_and_filter_results(content: str, results: list[dict]) -> tuple[list[dict], bool]:
    """Filter search results to only include sources actually referenced in the LLM answer.
    
    Returns (filtered_results, has_answer).
    """
    if not content:
        return results, bool(results)

    content_lower = content.lower().strip()
    
    # Detect "no answer found" responses
    no_answer_phrases = [
        "don't know",
        "do not know",
        "no information",
        "cannot find",
        "not found",
        "could not find this information",
        "could not find relevant",
        "no relevant information",
    ]
    if any(phrase in content_lower for phrase in no_answer_phrases):
        return [], False

    import re
    
    def normalize_source_name(name: str) -> str:
        """Normalize a source name for matching."""
        name = name.strip().strip('-*"\'').strip()
        # Remove common extensions for matching
        for ext in ['.pdf', '.docx', '.doc', '.pptx', '.txt', '.xlsx', '.csv']:
            if name.lower().endswith(ext):
                name = name[:-len(ext)]
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    
    # Extract source citations from the answer
    # Match patterns like:
    #   (Source: filename.pdf)
    #   Sources: file1, file2
    #   Source: filename
    cited_sources: set[str] = set()
    
    # Pattern 1: Inline citations like (Source: filename.pdf)
    inline_matches = re.findall(r'\(Source:\s*([^)]+)\)', content, re.IGNORECASE)
    for match in inline_matches:
        parts = re.split(r'[,;]', match)
        for p in parts:
            cleaned = p.strip().strip('-*"\'').strip()
            if cleaned:
                cited_sources.add(normalize_source_name(cleaned))
    
    # Pattern 2: Trailing "Sources: file1, file2" line
    trailing_match = re.search(r'sources?\:\s*(.+?)$', content, re.IGNORECASE | re.MULTILINE)
    if trailing_match:
        sources_str = trailing_match.group(1).strip()
        parts = re.split(r'[,;\n]', sources_str)
        for p in parts:
            cleaned = p.strip().strip('-*"\'').strip()
            if cleaned and len(cleaned) > 2:
                cited_sources.add(normalize_source_name(cleaned))
    
    if not cited_sources:
        # No explicit citations found — return all results as-is
        return results, bool(results)
    
    # Filter results to only include cited sources
    filtered = []
    for r in results:
        fname = (r.get("filename") or r.get("doc_name") or "").strip()
        if not fname:
            continue
        fname_norm = normalize_source_name(fname)
        # Match if any cited source is a substring of filename or vice versa
        if any(cs in fname_norm or fname_norm in cs for cs in cited_sources if cs):
            filtered.append(r)
    
    # If filtering removed everything (possible false negative), return original
    if not filtered and results:
        return results, True
    
    return filtered, bool(filtered)
