content = open('backend/app/routes/chat_sessions.py', 'r', encoding='utf-8').read()

# Add delete endpoint at the end before last line
delete_endpoint = """

@router.delete("/chat/sessions/{session_id}")
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
"""

if "delete_session" not in content:
    content = content.rstrip() + delete_endpoint
    open('backend/app/routes/chat_sessions.py', 'w', encoding='utf-8').write(content)
    print('Delete endpoint added')
else:
    print('Already exists')
