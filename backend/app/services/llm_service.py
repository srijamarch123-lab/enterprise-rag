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
<<<<<<< Updated upstream
- If the answer is NOT found in the context, say ONLY: "I could not find this information in the available documents." Do NOT show any sources.
- ALWAYS structure your answer as bullet points using "- " prefix.
- Keep your answers concise, proper, and focused by default (aim for 2 to 4 key bullet points).
- Provide a detailed and comprehensive answer with at least 5 distinct bullet points (aim for 5 to 10 points) ONLY if the user explicitly asks for a detailed explanation, elaboration, or in-depth overview.
- Each bullet point must be a specific, concise fact extracted from the documents.
- After each bullet point, cite the source document in parentheses, e.g., (Source: Compliance & Legal Framework Document.pdf)
- Be precise — cite exact figures, dates, names, locations, and policies from the documents.
- Do NOT copy-paste entire paragraphs from the documents. Synthesize and summarize.
- Do NOT invent information. If a specific detail is not in the context, do not guess.
- At the end, add a line: "Sources: " followed by a comma-separated list of all referenced document names.
- If multiple documents support the same fact, cite all of them."""
=======
- If the answer is NOT in the context, say only: "I could not find this information in the available documents."
- Format naturally: use bullet points for lists of 3+ items, short paragraph for simple facts, detailed paragraphs for complex topics. Let the question guide the format.
- Be concise and precise. Do not pad answers. Do not repeat information.
- Do not add a Sources section - sources are shown separately."""
>>>>>>> Stashed changes

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


def _gemini_stream(messages, max_tokens=900):
    try:
        import google.generativeai as genai
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("No Gemini API key configured")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m["content"] for m in messages if m["role"] != "system"]
        prompt = system + "\n\n" + "\n".join(user_msgs)
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        raise RuntimeError(f"Gemini failed: {e}")

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
            logger.warning("Groq also failed, falling back to Gemini: %s", e)

        # Fallback to Gemini
        try:
            return _gemini_chat(messages, max_tokens=max_tokens)
        except Exception as e:
            logger.error("Gemini also failed: %s", e)
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
                for token in _groq_stream(messages, max_tokens=max_tokens):
                    tokens_yielded = True
                    yield token
                return
            except Exception as e:
<<<<<<< Updated upstream
                if tokens_yielded:
                    logger.error("Groq stream failed mid-flight after tokens were yielded: %s", e)
                    return
                logger.warning("Groq stream failed before start, falling back to Gemini: %s", e)

        # Fallback to Gemini streaming if no tokens have been sent yet
        if not tokens_yielded:
            try:
                for token in _gemini_stream(messages, max_tokens=max_tokens):
                    tokens_yielded = True
                    yield token
                return
            except Exception as e:
                logger.error("Gemini stream also failed: %s", e)
                raise
=======
                logger.error("Groq stream also failed: %s", e)
                try:
                    logger.info("Falling back to Gemini")
                    yield from _gemini_stream(messages, max_tokens=max_tokens)
                except Exception as gemini_err:
                    logger.error("Gemini also failed: %s", gemini_err)
                    raise
>>>>>>> Stashed changes


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

    # Detect if user requested a detailed answer
    detailed_words = ["detailed", "detail", "elaborate", "comprehensive", "in-depth", "fully", "explain"]
    is_detailed_requested = any(w in query_lower for w in detailed_words)
    max_bullets = 7 if is_detailed_requested else 3

    # Extract sentences with source attribution
    query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]
    bullet_points: list[str] = []
    used_sources: list[str] = []

    for chunk in chunks:
        text = (chunk.get("text") or chunk.get("text_preview") or "").strip()
        fname = chunk.get("filename") or chunk.get("doc_name") or "Unknown"
        if not text:
            continue

        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        valid_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) >= 15 and len(sent) <= 300:
                # Score sentence by query keyword overlap
                sent_lower = sent.lower()
                score = sum(1 for w in query_words if w in sent_lower)
                valid_sentences.append((score, sent))

        if not valid_sentences:
            continue

        # Select up to 2 best sentences for this chunk (highest keyword scores)
        valid_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # 1. Best sentence
        best_sentence = valid_sentences[0][1]
        normalized = " ".join(best_sentence.lower().split())
        if not any(normalized in bp.lower() for bp in bullet_points):
            bullet_points.append(f"- {best_sentence} (Source: {fname})")
            if fname not in used_sources:
                used_sources.append(fname)
                
        # 2. Second best sentence (only if user requested detailed answer and it has relevant keyword overlap)
        if is_detailed_requested and len(valid_sentences) > 1 and valid_sentences[1][0] > 0:
            second_sentence = valid_sentences[1][1]
            normalized_2 = " ".join(second_sentence.lower().split())
            if not any(normalized_2 in bp.lower() for bp in bullet_points):
                bullet_points.append(f"- {second_sentence} (Source: {fname})")
                if fname not in used_sources:
                    used_sources.append(fname)

        if len(bullet_points) >= max_bullets:
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


def condense_query(query: str, history: list[dict]) -> str:
    """Rewrite a follow-up user query to incorporate relevant context from conversation history."""
    if not history:
        return query
    try:
        llm = LLMService(temperature=0.0)
        
        # Build clean history summary text
        history_text = ""
        for entry in history[-5:]:  # look at last 5 messages
            role = (entry.get("role") or "user").strip().lower()
            content = (entry.get("content") or "").strip()
            if content:
                history_text += f"{role.capitalize()}: {content}\n"
                
        if not history_text:
            return query
            
        prompt = (
            "Given the following conversation history and a follow-up question, rewrite the follow-up question to be a standalone search query that contains all necessary context (such as entity names, specific topics) from the history.\n"
            "Do NOT answer the question. Just output the rewritten standalone query. If the question is already standalone and does not need context, output it exactly as is.\n\n"
            f"Conversation History:\n{history_text}\n"
            f"Follow-up Question: {query}\n"
            "Standalone Query:"
        )
        rewritten = llm.chat_completion(messages=[{"role": "user", "content": prompt}], max_tokens=150)
        rewritten = rewritten.strip().strip('"\'-*')
        if rewritten:
            logger.info("Rewrote follow-up query '%s' to standalone query '%s'", query, rewritten)
            return rewritten
    except Exception as e:
        logger.warning("Failed to condense follow-up query via LLM: %s. Using rule-based fallback.", e)

    # Rule-based fallback for query condensation when LLM is unavailable
    try:
        query_lower = query.lower().strip()
        # Common follow-up triggers or short questions
        follow_up_triggers = [
            "summarize", "summary", "key points", "points", "elaborate", "explain",
            "more details", "tell me more", "why", "how", "what else", "relate to this",
            "show key points"
        ]
        is_follow_up = len(query.split()) <= 6 or any(trigger in query_lower for trigger in follow_up_triggers)
        if is_follow_up:
            # Find the last user query in history
            last_user_query = None
            for entry in reversed(history):
                if entry.get("role") == "user":
                    last_user_query = entry.get("content")
                    break
            if last_user_query:
                # Clean punctuation and combine query with key content words of the previous question
                import re
                clean_words = []
                for w in last_user_query.split():
                    w_clean = re.sub(r'[^\w\s-]', '', w)
                    if w_clean and w_clean.lower() not in [
                        "what", "is", "are", "the", "a", "an", "of", "in", "to", "for", "with", "on", "at", "by", "from", "do", "play", "how", "why"
                    ]:
                        clean_words.append(w_clean)
                keywords = " ".join(clean_words[:6]) # extract first few keywords
                combined = f"{query} {keywords}".strip()
                logger.info("Rule-based condensed query: '%s'", combined)
                return combined
    except Exception as rule_err:
        logger.warning("Rule-based query condensation also failed: %s", rule_err)

    return query


def _map_messages_to_gemini(messages: List[Any]) -> tuple[Optional[dict], list[dict]]:
    system_instruction = None
    contents = []
    
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        
        if role == "system":
            system_instruction = {
                "parts": [{"text": content}]
            }
        elif role == "user":
            contents.append({
                "role": "user",
                "parts": [{"text": content}]
            })
        elif role == "assistant" or role == "model":
            contents.append({
                "role": "model",
                "parts": [{"text": content}]
            })
        elif role == "tool":
            contents.append({
                "role": "user",
                "parts": [{"text": f"Tool output: {content}"}]
            })
            
    return system_instruction, contents


def _gemini_chat(messages: List[Any], max_tokens: int = 1024) -> str:
    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Gemini API key not configured")
        
    system_inst, contents = _map_messages_to_gemini(messages)
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": max_tokens
        }
    }
    if system_inst:
        payload["systemInstruction"] = system_inst
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    
    import requests
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip() if text else ""
    except (KeyError, IndexError):
        logger.warning("Unexpected Gemini response format: %s", data)
        return ""


def _gemini_stream(messages: List[Any], max_tokens: int = 1024):
    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Gemini API key not configured")
        
    system_inst, contents = _map_messages_to_gemini(messages)
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": max_tokens
        }
    }
    if system_inst:
        payload["systemInstruction"] = system_inst
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key={key}"
    
    import requests
    import json
    
    response = requests.post(url, json=payload, stream=True, timeout=30)
    response.raise_for_status()
    
    for line in response.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8").strip()
        if line_str.startswith("data:"):
            data_json = line_str[5:].strip()
            if not data_json:
                continue
            try:
                chunk = json.loads(data_json)
                text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                if text:
                    yield text
            except Exception:
                pass


