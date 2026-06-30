from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.rbac import require_admin
from app.models import User, UserRole
from app.services.auth import get_current_user
from app.services.audit import log_action


router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleUpdateRequest(BaseModel):
    user_id: int
    role: UserRole


@router.get("/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    from app.models import AuditLog

    users = db.query(User).all()

    # Get last login IP for each user
    user_last_login_ip = {}
    # Get login count per user
    user_login_count = {}
    # Get last 3 actions per user
    user_recent_actions = {}
    # Get password reset date per user
    user_password_reset = {}

    all_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    for log in all_logs:
        uid = log.user_id
        if uid:
            # Last login IP (most recent login action)
            if log.action == "login" and uid not in user_last_login_ip:
                user_last_login_ip[uid] = log.ip_address
            # Login count
            if log.action == "login":
                user_login_count[uid] = user_login_count.get(uid, 0) + 1
            # Password reset
            if log.action == "password_reset":
                user_password_reset[uid] = log.timestamp.isoformat()
            # Recent actions (last 3)
            if uid not in user_recent_actions:
                user_recent_actions[uid] = []
            if len(user_recent_actions[uid]) < 3:
                user_recent_actions[uid].append({
                    "action": log.action,
                    "timestamp": log.timestamp.isoformat(),
                })

    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "last_login_ip": user_last_login_ip.get(u.id),
            "login_count": user_login_count.get(u.id, 0),
            "password_last_changed": user_password_reset.get(u.id),
            "recent_activity": user_recent_actions.get(u.id, []),
        }
        for u in users
    ]


@router.put("/users/role", dependencies=[Depends(require_admin)])
def update_role(
    body: RoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")


    user.role = body.role
    user.token_version += 1  # invalidate existing tokens
    db.commit()

    log_action(
        db,
        action="role_change",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details={"role": str(body.role)},
    )

    return {"message": f"Role updated to {body.role} for user {user.email}"}



@router.put("/users/{user_id}/disable", dependencies=[Depends(require_admin)])
def disable_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    user.token_version += 1
    db.commit()


    log_action(
        db,
        action="disable_user",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details=None,
    )

    return {"message": f"User {user.email} disabled"}


@router.put("/users/{user_id}/enable", dependencies=[Depends(require_admin)])
def enable_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.token_version += 1
    db.commit()

    log_action(
        db,
        action="enable_user",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details=None,
    )

    return {"message": f"User {user.email} enabled"}


@router.post("/users/{user_id}/force-logout", dependencies=[Depends(require_admin)])
def force_logout(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.token_version += 1
    db.commit()


    log_action(
        db,
        action="force_logout",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details={"email": user.email},
    )

    return {"message": f"User {user.email} forcefully logged out"}


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def get_audit_logs(
    skip: int = 0,
    limit: int = 50,
    action: str | None = None,
    db: Session = Depends(get_db),
):
    from app.models import AuditLog

    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    logs = (
        query.order_by(AuditLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "user_email": l.details.get("email") if l.details else (l.user.email if l.user else None),
            "user_role": l.details.get("role") if l.details else (l.user.role if l.user else None),
            "action": l.action,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "ip_address": l.ip_address,
            "details": l.details,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
        }
        for l in logs
    ]


@router.get("/login-activity", dependencies=[Depends(require_admin)])
def get_login_activity(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get login activity logs with user details (email, role, IP)."""
    from app.models import AuditLog

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(["login", "logout"]))
        .order_by(AuditLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "user_email": l.details.get("email") if l.details else (l.user.email if l.user else None),
            "user_role": l.details.get("role") if l.details else (l.user.role if l.user else None),
            "action": l.action,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "ip_address": l.ip_address,
        }
        for l in logs
    ]


@router.get("/stats", dependencies=[Depends(require_admin)])
def get_stats(db: Session = Depends(get_db)):
    """Get admin dashboard stats."""
    from app.models import AuditLog
    from datetime import datetime, timedelta

    # Total users
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()  # noqa: E712

    # Logins today - use last 24 hours instead of date comparison to avoid timezone issues
    yesterday = datetime.utcnow() - timedelta(days=1)
    logins_today = (
        db.query(AuditLog)
        .filter(AuditLog.action == "login", AuditLog.timestamp >= yesterday)
        .count()
    )

    # Failed attempts today
    failed_today = (
        db.query(AuditLog)
        .filter(AuditLog.action == "login_failed", AuditLog.timestamp >= yesterday)
        .count()
    )

    # Users by role
    role_counts = {}
    for role_name in ['admin', 'hr', 'manager', 'employee']:
        role = UserRole(role_name)
        count = db.query(User).filter(User.role == role).count()
        role_counts[role_name] = count

    return {
        "total_users": total_users,
        "active_users": active_users,
        "logins_today": logins_today,
        "failed_attempts_today": failed_today,
        "users_by_role": role_counts,
    }


class PromoteByEmailRequest(BaseModel):
    email: str


@router.post("/users/promote-to-admin", dependencies=[Depends(require_admin)])
def promote_to_admin(
    body: PromoteByEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found with that email")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="User is already an admin")
    user.role = UserRole.admin
    user.token_version += 1
    db.commit()
    log_action(
        db,
        action="role_change",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details={"role": "admin", "promoted_by_email": True},
    )
    return {"message": f"{user.email} is now an admin", "user_id": user.id}
