"""
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/refresh
GET  /api/auth/me

POST /api/auth/reset-password/request
POST /api/auth/reset-password/confirm

Admin user management:
GET  /api/users
PUT  /api/users/{id}/role
PUT  /api/users/{id}/disable
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, AuditLog, PasswordResetToken
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    require_role,
    create_reset_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    role: UserRole = UserRole.employee


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RoleUpdate(BaseModel):
    role: UserRole


class ResetRequestBody(BaseModel):
    email: EmailStr


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str


# ─── Helpers ────────────────────────────────────────────────────────────────


def _log(db: Session, user_id: int | None, action: str, **kwargs):
    db.add(AuditLog(user_id=user_id, action=action, **kwargs))
    db.commit()


# ─── Auth endpoints ─────────────────────────────────────────────────────────


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    payload = {"sub": user.id, "role": user.role, "tv": user.token_version}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    user.last_login = datetime.utcnow()
    db.commit()
    _log(db, user.id, "login")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role,
    }


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _log(db, current_user.id, "logout")
    return {"message": "Logged out"}


@router.post("/refresh")
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Not a refresh token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")

    new_payload = {"sub": user.id, "role": user.role, "tv": user.token_version}
    return {"access_token": create_access_token(new_payload), "token_type": "bearer"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "last_login": current_user.last_login,
    }


# ─── Password reset ─────────────────────────────────────────────────────────


@router.post("/reset-password/request")
def reset_request(body: ResetRequestBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()

    # Always return 200 to avoid leaking whether an email exists.
    if not user:
        return {"message": "If that email exists, a reset token has been generated"}

    token = create_reset_token(user.id, db)

    # Dev mode: return token directly.
    return {"message": "Reset token generated (dev mode)", "reset_token": token}


@router.post("/reset-password/confirm")
def reset_confirm(body: ResetConfirmBody, db: Session = Depends(get_db)):
    entry = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == body.token, PasswordResetToken.used == False)  # noqa: E712
        .first()
    )

    if not entry:
        raise HTTPException(400, "Invalid or already used token")
    if entry.expires_at < datetime.utcnow():
        raise HTTPException(400, "Reset token has expired")

    user = db.query(User).filter(User.id == entry.user_id).first()
    if not user:
        raise HTTPException(400, "User not found")

    user.hashed_password = hash_password(body.new_password)
    user.token_version += 1  # invalidate all existing sessions
    entry.used = True
    db.commit()

    _log(db, user.id, "password_reset")
    return {"message": "Password updated successfully"}


# ─── Admin user management ────────────────────────────────────────────────


@users_router.get("")
def list_users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "last_login": u.last_login,
        }
        for u in users
    ]


@users_router.put("/{user_id}/role")
def update_role(
    user_id: int,
    body: RoleUpdate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    old_role = user.role
    user.role = body.role
    user.token_version += 1  # invalidate existing tokens
    db.commit()

    _log(
        db,
        admin.id,
        "role_change",
        resource_type="user",
        resource_id=str(user_id),
        details={"from": old_role, "to": body.role},
    )

    return {"id": user_id, "role": user.role}


@users_router.put("/{user_id}/disable")
def disable_user(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.is_active = False
    user.token_version += 1
    db.commit()

    _log(
        db,
        admin.id,
        "disable_user",
        resource_type="user",
        resource_id=str(user_id),
    )

    return {"id": user_id, "is_active": False}


@users_router.put("/{user_id}/revoke")
def revoke_role(
    user_id: int,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Revoke elevated access by setting user role back to default employee.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    old_role = user.role
    user.role = UserRole.employee
    user.token_version += 1
    db.commit()

    _log(
        db,
        admin.id,
        "role_revoke",
        resource_type="user",
        resource_id=str(user_id),
        details={"from": old_role, "to": UserRole.employee},
    )

    return {"id": user_id, "role": user.role}

