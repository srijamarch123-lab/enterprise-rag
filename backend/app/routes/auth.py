"""
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
POST /api/auth/refresh
GET  /api/auth/me

POST /api/auth/reset-password/request
POST /api/auth/reset-password/confirm
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
    create_reset_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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



