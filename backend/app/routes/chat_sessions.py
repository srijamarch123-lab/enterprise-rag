from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage, ChatSession, User
from app.routes.search_v1 import ChatRequest, search
from app.services.auth import get_current_user
from app.services.llm_service import build_chat_prompt, build_fallback_answer, LLMService, generate_suggested_questions, assemble_context

router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str


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

    from app.models import Feedback
    message_ids = [msg.id for msg in session.messages]
    feedbacks = db.query(Feedback).filter(
        Feedback.message_id.in_(message_ids),
        Feedback.user_id == current_user.id
    ).all() if message_ids else []
    feedback_map = {f.message_id: ("up" if f.is_helpful else "down") for f in feedbacks}

    return {
        "id": session.id,
        "title": session.title,
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "metadata": {
                    **(message.message_metadata or {}),
                    "feedbackSubmitted": feedback_map.get(message.id),
                },
            }
            for message in session.messages
        ],
    }



@router.post("/sessions/{session_id}/messages/stream")
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
    db.commit()
    db.refresh(user_message)

    history_messages = [
        {"role": message.role, "content": message.content or ""}
        for message in session.messages
    ]

    search_request = ChatRequest(query=req.content, limit=5)
    search_response = search(search_request, current_user=current_user, db=db)
    chunks = search_response.get("results", [])

    # Exclude the user message we just added from history, since it is passed as the current query
    history_for_prompt = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_messages[:-1]
    ]

    prompt_messages = build_chat_prompt(req.content, chunks, history_messages=history_for_prompt)
    if not prompt_messages:
        prompt_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": req.content.strip()},
        ]

    def event_stream():
        assistant_chunks: list[str] = []
        try:
            llm = LLMService()
            for token in llm.stream_chat_completion(prompt_messages, max_tokens=900):
                assistant_chunks.append(token)
                yield f"data: {token}\n\n"
            final_text = "".join(assistant_chunks).strip()
            if not final_text:
                final_text = build_fallback_answer(req.content, chunks)
            results = search_response.get("results", [])

            # Generate follow-up suggestions using the LLM based on RAG context
            context_text = assemble_context(chunks)
            suggestions = generate_suggested_questions(req.content, final_text, context_text)

            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=final_text,
                message_metadata={
                    "answer": final_text,
                    "results": results,
                    "has_answer": search_response.get("has_answer", False),
                    "suggestions": suggestions,
                },
            )
            db.add(assistant_message)
            session.updated_at = __import__("datetime").datetime.utcnow()
            session.title = session.title if session.title != "New chat" else (req.content.strip()[:40] or session.title)
            db.commit()
            yield f"data: {__import__('json').dumps({'message_id': assistant_message.id, 'answer': final_text, 'results': results, 'has_answer': search_response.get('has_answer', False), 'suggestions': suggestions})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive fallback
            final_text = build_fallback_answer(req.content, chunks)
            suggestions = ["Summarize the sources", "Show the key points", "What other documents relate to this?"]
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=final_text,
                message_metadata={
                    "answer": final_text,
                    "results": chunks,
                    "has_answer": bool(chunks),
                    "suggestions": suggestions,
                }
            )
            db.add(assistant_message)
            db.commit()
            yield f"data: {__import__('json').dumps({'message_id': assistant_message.id, 'answer': final_text, 'results': chunks, 'has_answer': bool(chunks), 'suggestions': suggestions})}\n\n"


    return StreamingResponse(event_stream(), media_type="text/event-stream")

