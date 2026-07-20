from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.rbac import require_admin
from app.models import Feedback, ChatMessage, User, ChatSession
from app.services.auth import get_current_user
from app.services.audit import log_action

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackCreateRequest(BaseModel):
    message_id: int
    is_helpful: bool
    comment: Optional[str] = None


class FeedbackResolveRequest(BaseModel):
    status: str  # flagged | reviewed | resolved
    admin_notes: Optional[str] = None


@router.post("/feedback", status_code=201)
def submit_feedback(
    body: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify the message exists
    msg = db.query(ChatMessage).filter(ChatMessage.id == body.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Chat message not found")

    # Check if feedback already exists for this message by this user
    feedback = db.query(Feedback).filter(
        Feedback.message_id == body.message_id,
        Feedback.user_id == current_user.id
    ).first()

    if feedback:
        feedback.is_helpful = body.is_helpful
        feedback.comment = body.comment
        feedback.status = "flagged" if not body.is_helpful else "reviewed"
        feedback.created_at = datetime.utcnow()
    else:
        feedback = Feedback(
            message_id=body.message_id,
            user_id=current_user.id,
            is_helpful=body.is_helpful,
            comment=body.comment,
            status="flagged" if not body.is_helpful else "reviewed"
        )
        db.add(feedback)

    db.commit()
    db.refresh(feedback)

    # Log audit action
    log_action(
        db,
        action="submit_feedback",
        user_id=current_user.id,
        resource_type="feedback",
        resource_id=str(feedback.id),
        details={"is_helpful": body.is_helpful, "message_id": body.message_id}
    )

    return {"message": "Feedback submitted successfully", "id": feedback.id}


@router.get("/admin/feedback", dependencies=[Depends(require_admin)])
def list_feedback(
    status: Optional[str] = None,
    is_helpful: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Feedback)
    if status:
        query = query.filter(Feedback.status == status)
    if is_helpful is not None:
        query = query.filter(Feedback.is_helpful == is_helpful)

    feedbacks = query.order_by(Feedback.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for f in feedbacks:
        msg = f.message
        user = f.user

        # Retrieve corresponding user query
        user_query = None
        if msg and msg.session_id:
            prev_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == "user",
                ChatMessage.id < msg.id
            ).order_by(ChatMessage.id.desc()).first()
            if prev_msg:
                user_query = prev_msg.content

        results.append({
            "id": f.id,
            "message_id": f.message_id,
            "user_id": f.user_id,
            "user_email": user.email if user else None,
            "query": user_query or "Unknown query",
            "assistant_response": msg.content if msg else None,
            "is_helpful": f.is_helpful,
            "comment": f.comment,
            "status": f.status,
            "admin_notes": f.admin_notes,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })
    return results


@router.put("/admin/feedback/{feedback_id}", dependencies=[Depends(require_admin)])
def resolve_feedback(
    feedback_id: int,
    body: FeedbackResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.status = body.status
    if body.admin_notes is not None:
        feedback.admin_notes = body.admin_notes

    db.commit()

    # Log audit action
    log_action(
        db,
        action="resolve_feedback",
        user_id=current_user.id,
        resource_type="feedback",
        resource_id=str(feedback.id),
        details={"status": body.status}
    )

    return {"message": "Feedback updated successfully", "id": feedback.id}


@router.get("/admin/feedback-analytics", dependencies=[Depends(require_admin)])
def get_feedback_analytics(db: Session = Depends(get_db)):
    # 1. Total counts
    total_upvotes = db.query(Feedback).filter(Feedback.is_helpful == True).count()
    total_downvotes = db.query(Feedback).filter(Feedback.is_helpful == False).count()

    # 2. Aggregations from downvotes
    downvoted_feedbacks = db.query(Feedback).filter(Feedback.is_helpful == False).all()

    query_counts = {}
    doc_counts = {}

    for f in downvoted_feedbacks:
        msg = f.message
        if not msg:
            continue

        # Find query
        user_query = None
        if msg.session:
            prev_msg = db.query(ChatMessage).filter(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == "user",
                ChatMessage.created_at <= msg.created_at,
                ChatMessage.id < msg.id
            ).order_by(ChatMessage.created_at.desc()).first()
            if prev_msg:
                user_query = prev_msg.content

        user_query = user_query or "Unknown query"

        # Aggregate query
        if user_query not in query_counts:
            query_counts[user_query] = {"query": user_query, "count": 0, "docs": set()}
        query_counts[user_query]["count"] += 1

        # Aggregate documents cited
        metadata = msg.message_metadata or {}
        results = metadata.get("results") or []
        for r in results:
            doc_name = r.get("filename") or r.get("doc_name") or "Unknown Document"
            query_counts[user_query]["docs"].add(doc_name)
            doc_counts[doc_name] = doc_counts.get(doc_name, 0) + 1

    # Format queries
    sorted_queries = []
    for q_text, info in query_counts.items():
        sorted_queries.append({
            "query": info["query"],
            "count": info["count"],
            "docs": list(info["docs"])
        })
    sorted_queries.sort(key=lambda x: x["count"], reverse=True)

    # Format docs
    sorted_docs = [{"filename": k, "count": v} for k, v in doc_counts.items()]
    sorted_docs.sort(key=lambda x: x["count"], reverse=True)

    return {
        "upvotes": total_upvotes,
        "downvotes": total_downvotes,
        "most_downvoted_queries": sorted_queries[:10],
        "most_downvoted_documents": sorted_docs[:10]
    }
