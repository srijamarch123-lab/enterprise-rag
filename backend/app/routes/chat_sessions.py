from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage, ChatSession, User
from app.routes.search_v1 import ChatRequest, search
from app.services.auth import get_current_user
from app.services.llm_service import build_chat_prompt, build_fallback_answer, LLMService, generate_suggested_questions, assemble_context, parse_and_filter_results
from app.config.settings import get_settings
from app.services.limiter import limiter

settings = get_settings()
router = APIRouter(prefix="/api/chat", tags=["chat"])




class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    session_context: str | None = None
    session_doc_name: str | None = None
    department: str | None = None
    file_type: str | None = None
    date_range: str | None = None
    session_doc_ids: list[int] | None = None


@router.post("/sessions", status_code=201)
def create_session(
    req: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = ChatSession(user_id=current_user.id, title=req.title or "New chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "created_at": session.created_at}


@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
        for session in sessions
    ]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.models import Feedback, Document, Chunk

    message_ids = [msg.id for msg in session.messages]
    feedbacks = db.query(Feedback).filter(
        Feedback.message_id.in_(message_ids),
        Feedback.user_id == current_user.id
    ).all() if message_ids else []
    feedback_map = {f.message_id: ("up" if f.is_helpful else "down") for f in feedbacks}

    def normalize_filename(name: str) -> str:
        if not name:
            return ""
        import re
        try:
            b = name.encode('latin-1')
            name = b.decode('cp1252')
        except Exception:
            pass
        name = name.replace('\x96', '-')
        name = name.replace('\u2013', '-')
        name = name.replace('\u2014', '-')
        return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

    def _enrich_results(res_list):
        if not isinstance(res_list, list):
            return res_list
        enriched = []
        for r in res_list:
            if not isinstance(r, dict):
                enriched.append(r)
                continue
            r_copy = dict(r)
            doc_id = r_copy.get("document_id")
            filename = r_copy.get("filename")
            doc = None
            
            # 1. Match document by normalized filename (original_filename in SQLite) first to avoid ID mismatches
            if filename:
                norm_q = normalize_filename(filename)
                all_docs = db.query(Document).all()
                for d in all_docs:
                    if normalize_filename(d.original_filename) == norm_q:
                        doc = d
                        break
            # 2. DO NOT fall back to doc_id if filename is present but failed to match (stale Qdrant document)
            # Only use doc_id fallback if filename is completely missing/empty
            if not doc and doc_id and not filename:
                doc = db.query(Document).filter(Document.id == doc_id).first()
                
            if doc:
                r_copy["document_id"] = doc.id
                r_copy["file_path"] = doc.file_path
                r_copy["doc_name"] = doc.original_filename
                r_copy["filename"] = doc.original_filename
                if doc.drive_file_id:
                    r_copy["drive_file_id"] = doc.drive_file_id
                    r_copy["drive_url"] = f"https://drive.google.com/file/d/{doc.drive_file_id}/view"
            
            # 2. Match chunk by index under the resolved document to ensure correct text is retrieved
            chunk_id = r_copy.get("chunk_id")
            chunk_index = r_copy.get("chunk_index")
            chunk = None
            if doc and chunk_index is not None:
                chunk = db.query(Chunk).filter(Chunk.document_id == doc.id, Chunk.chunk_index == chunk_index).first()
            if not chunk and chunk_id:
                chunk = db.query(Chunk).filter(Chunk.id == chunk_id).first()
                
            if chunk:
                r_copy["chunk_id"] = chunk.id
                r_copy["text"] = chunk.parent_text if chunk.parent_text else chunk.text
                r_copy["parent_text"] = chunk.parent_text
                r_copy["text_preview"] = chunk.text[:200]
            else:
                if not r_copy.get("text"):
                    r_copy["text"] = r_copy.get("parent_text") or r_copy.get("text_preview") or ""
                if not r_copy.get("text_preview") and r_copy.get("text"):
                    r_copy["text_preview"] = r_copy["text"][:200]

            # Recalibrate score for historical messages if uncalibrated (>= 0.99 or missing)
            cs = float(r_copy.get("confidence_score") or r_copy.get("combined_score") or 0.0)
            sem = float(r_copy.get("semantic_score", 0.0) or 0.0)
            if cs >= 0.99 or cs <= 0:
                if sem > 0:
                    recalibrated = min(0.98, max(0.40, sem))
                else:
                    recalibrated = 0.85
                r_copy["combined_score"] = round(recalibrated, 4)
                r_copy["confidence_score"] = round(recalibrated, 4)

            enriched.append(r_copy)
        return enriched

    formatted_messages = []
    for message in session.messages:
        meta = dict(message.message_metadata or {})
        if "results" in meta:
            meta["results"] = _enrich_results(meta["results"])
        
        # Parse content of assistant messages to fix incorrect sources/has_answer for all chats (even historical ones)
        if message.role == "assistant":
            filtered_results, has_answer = parse_and_filter_results(message.content or "", meta.get("results", []))
            meta["results"] = filtered_results
            meta["has_answer"] = has_answer

        meta["feedbackSubmitted"] = feedback_map.get(message.id)
        formatted_messages.append({
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "metadata": meta,
        })

    session_metadata = session.session_metadata or {}
    uploaded_ids = session_metadata.get("uploaded_document_ids", [])
    session_docs_list = []
    if uploaded_ids:
        docs = db.query(Document).filter(Document.id.in_(uploaded_ids)).all()
        for doc in docs:
            session_docs_list.append({
                "id": doc.id,
                "filename": doc.original_filename
            })

    return {
        "id": session.id,
        "title": session.title,
        "session_doc": session_metadata.get("session_doc"),
        "session_doc_name": session_metadata.get("session_doc_name"),
        "session_docs": session_docs_list,
        "messages": formatted_messages,
    }



def truncate_chat_history(history: list[dict], max_tokens: int = 1500) -> list[dict]:
    """
    Keep only the most recent messages from history that fit within the token limit.
    """
    from app.services.llm_service import count_tokens
    truncated = []
    total_tokens = 0
    for msg in reversed(history):
        content = msg.get("content") or ""
        msg_tokens = count_tokens(content) + 10  # approximate overhead
        if total_tokens + msg_tokens > max_tokens:
            break
        truncated.append(msg)
        total_tokens += msg_tokens
    return list(reversed(truncated))


@router.post("/sessions/{session_id}/messages/stream")
@limiter.limit(settings.rate_limit_chat)
def stream_chat(
    session_id: int,
    req: SendMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    user_message = ChatMessage(session_id=session.id, role="user", content=req.content.strip())
    db.add(user_message)

    # Save uploaded doc to session metadata if provided
    session_metadata = session.session_metadata or {}
    session_doc_ids = session_metadata.get("uploaded_document_ids", [])
    if req.session_doc_ids:
        uploaded_ids = list(session_doc_ids)
        for doc_id in req.session_doc_ids:
            if doc_id not in uploaded_ids:
                uploaded_ids.append(doc_id)
        session.session_metadata = {
            **session_metadata,
            "uploaded_document_ids": uploaded_ids
        }
        session_doc_ids = uploaded_ids

    if req.session_context:
        existing_meta = session.session_metadata or {}
        existing_docs = existing_meta.get("session_docs", [])
        new_doc = {"name": req.session_doc_name or "uploaded_document", "text": req.session_context}
        existing_docs.append(new_doc)
        session.session_metadata = {
            **existing_meta,
            "session_docs": existing_docs,
            "session_doc": req.session_context,
            "session_doc_name": req.session_doc_name or "uploaded_document"
        }

    # Update session title if it's the default "New chat"
    if session.title == "New chat":
        session.title = req.content.strip()[:40] or "New chat"
        session.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(user_message)

    history_messages = [
        {"role": message.role, "content": message.content or ""}
        for message in session.messages
    ]

    # 1. Define tools for OpenAI/Groq function calling
    tools: list[Any] = [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Searches the enterprise document database for relevant chunks, policies, guidelines, and context matching the query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query/keywords to locate relevant document sections."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # Exclude the user message we just added from history, since it is passed as the current query
    history_for_prompt = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_messages[:-1]
    ]

    # Implement sliding history window (allow up to 4000 tokens for follow-ups)
    history_for_prompt = truncate_chat_history(history_for_prompt, max_tokens=4000)

    # Condense search query using history to make follow-up questions context-aware
    from app.services.llm_service import condense_query
    condensed_query = condense_query(req.content.strip(), history_for_prompt)

    # Pre-run search for fallback (used if LLM agent fails or tools are not supported)
    search_request = ChatRequest(
        query=condensed_query,
        limit=12,
        department=req.department,
        file_type=req.file_type,
        date_range=req.date_range,
        document_ids=session_doc_ids if session_doc_ids else None,
    )
    search_response = search(search_request, current_user=current_user, db=db)
    chunks = search_response.get("results", [])

    # Inject uploaded session document as extra context (legacy fallback only)
    extra_chunks = []
    existing_meta = session.session_metadata or {}
    session_docs = existing_meta.get("session_docs", [])
    has_uploaded_doc = bool(session_doc_ids or req.session_context or session_docs)
    
    if not session_doc_ids:
        if req.session_context:
            doc_text = req.session_context
            # Split into paragraphs and find most relevant to current query
            query_lower = req.content.lower()
            paragraphs = [p.strip() for p in doc_text.split('\n') if len(p.strip()) > 50]
            # Score paragraphs by keyword overlap with query
            query_words = set(w for w in query_lower.split() if len(w) > 3)
            scored = []
            for p in paragraphs:
                score = sum(1 for w in query_words if w in p.lower())
                scored.append((score, p))
            scored.sort(reverse=True)
            # Take top relevant paragraphs up to 3000 chars
            selected = []
            total = 0
            for score, p in scored:
                if total + len(p) > 3000:
                    break
                selected.append(p)
                total += len(p)
            # Also include first 500 chars for context
            intro = doc_text[:500]
            final_text = intro + "\n\n" + "\n".join(selected) if selected else doc_text[:3000]
            extra_chunks.append({"text": final_text, "filename": req.session_doc_name or "uploaded_document", "combined_score": 1.0})
        elif session_docs:
            for doc in session_docs:
                doc_text = doc["text"]
                for marker in ['Use this as additional context', 'The user has uploaded']:
                    if marker in doc_text:
                        idx = doc_text.find('\n\n', doc_text.find(marker))
                        if idx > 0:
                            doc_text = doc_text[idx+2:]
                        break
                extra_chunks.append({"text": doc_text, "filename": doc["name"], "combined_score": 1.0})
                
    final_chunks = extra_chunks if (has_uploaded_doc and not session_doc_ids) else extra_chunks + chunks
    prompt_messages = build_chat_prompt(req.content, final_chunks, history_messages=history_for_prompt)
    if not prompt_messages:
        prompt_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": req.content.strip()},
        ]

    # Set up ReAct agentic history
    from app.services.llm_service import SYSTEM_PROMPT, assemble_context
    agent_messages: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    for msg in history_for_prompt:
        agent_messages.append({"role": msg["role"], "content": msg["content"]})
    agent_messages.append({"role": "user", "content": req.content.strip()})

    client = None
    if settings.openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
        except Exception:
            pass

    agent_chunks = extra_chunks if (has_uploaded_doc and not session_doc_ids) else list(chunks)
    agent_ran_tools = False

    # Run agent loop if client is available AND (either no uploaded doc, or we have the doc IDs in Qdrant)
    run_agent_loop = client is not None and (not has_uploaded_doc or bool(session_doc_ids))

    if run_agent_loop:
        # Run agentic tool calling loop (max 3 turns)
        max_turns = 3
        turn = 0
        while turn < max_turns:
            turn += 1
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=agent_messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.0,
                )
                choice = response.choices[0]
                message = choice.message
                
                if message.tool_calls:
                    agent_ran_tools = True
                    tool_calls_payload = []
                    for tc in message.tool_calls:
                        tool_calls_payload.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })
                    agent_messages.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": tool_calls_payload
                    })
                    
                    for tc in message.tool_calls:
                        if tc.function.name == "search_documents":
                            import json
                            args = json.loads(tc.function.arguments)
                            search_q = args.get("query", req.content)
                            
                            search_req_t = ChatRequest(
                                query=search_q,
                                limit=12,
                                department=req.department,
                                file_type=req.file_type,
                                date_range=req.date_range,
                                document_ids=session_doc_ids if session_doc_ids else None,
                            )
                            search_res_t = search(search_req_t, current_user=current_user, db=db)
                            new_chunks = search_res_t.get("results", [])
                            
                            for nc in new_chunks:
                                if nc.get("chunk_id") not in {c.get("chunk_id") for c in agent_chunks}:
                                    agent_chunks.append(nc)
                            
                            observation = assemble_context(new_chunks)
                            if not observation:
                                observation = "No relevant document sections found matching the query."
                                
                            agent_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.function.name,
                                "content": observation
                            })
                    continue
                else:
                    break
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Agentic tool call turn failed, breaking loop: %s", e)
                break

    def event_stream():
        assistant_chunks: list[str] = []
        try:
            openai_success = False
            if client:
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=agent_messages,
                        temperature=0.0,
                        stream=True,
                    )
                    for chunk in response:
                        content = chunk.choices[0].delta.content if chunk.choices else None
                        if content:
                            assistant_chunks.append(content)
                            yield f"data: {content}\n\n"
                    openai_success = True
                except Exception as openai_err:
                    import logging
                    logging.getLogger(__name__).warning("OpenAI failed, falling back to Groq: %s", openai_err)
                    assistant_chunks = []
            if not openai_success:
                llm = LLMService()
                for token in llm.stream_chat_completion(prompt_messages, max_tokens=900):
                    assistant_chunks.append(token)
                    yield f"data: {token}\n\n"

            final_text = "".join(assistant_chunks).strip()
            if not final_text:
                final_text = build_fallback_answer(req.content, agent_chunks)
                yield f"data: {final_text}\n\n"

            filtered_results, has_answer = parse_and_filter_results(final_text, agent_chunks)

            # Generate follow-up suggestions using the LLM based on RAG context
            context_text = assemble_context(agent_chunks)
            suggestions = generate_suggested_questions(req.content, final_text, context_text)

            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=final_text,
                message_metadata={
                    "answer": final_text,
                    "results": filtered_results,
                    "has_answer": has_answer,
                    "suggestions": suggestions,
                },
            )
            db.add(assistant_message)
            session.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None)
            session.title = session.title if session.title != "New chat" else (req.content.strip()[:40] or session.title)
            db.commit()
            yield f"data: {__import__('json').dumps({'user_message_id': user_message.id, 'message_id': assistant_message.id, 'answer': final_text, 'results': filtered_results, 'has_answer': has_answer, 'suggestions': suggestions})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive fallback
            import logging
            logging.getLogger(__name__).error("Stream error: %s", exc, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
            final_text = build_fallback_answer(req.content, agent_chunks)
            suggestions = ["Summarize the sources", "Show the key points", "What other documents relate to this?"]
            
            filtered_results, has_answer = parse_and_filter_results(final_text, agent_chunks)
            
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=final_text,
                message_metadata={
                    "answer": final_text,
                    "results": filtered_results,
                    "has_answer": has_answer,
                    "suggestions": suggestions,
                }
            )
            db.add(assistant_message)
            db.commit()
            yield f"data: {__import__('json').dumps({'user_message_id': user_message.id, 'message_id': assistant_message.id, 'answer': final_text, 'results': filtered_results, 'has_answer': has_answer, 'suggestions': suggestions})}\n\n"


    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}
