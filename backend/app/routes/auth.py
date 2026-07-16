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
from fastapi import APIRouter, Depends, HTTPException, Response, Request
import logging

from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, AuditLog, PasswordResetToken
from typing import TYPE_CHECKING

from fastapi import Cookie

from app.services.auth import (

    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    set_jwt_cookie,
    clear_jwt_cookie,
    verify_password,
    create_reset_token,
)

from app.config.settings import get_settings

logger = logging.getLogger(__name__)



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


from app.services.limiter import limiter


# ─── Auth endpoints ─────────────────────────────────────────────────────────


def register(req: RegisterRequest, db: Session = Depends(get_db)):
    email_norm = req.email.lower().strip()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=email_norm,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "email": user.email, "role": user.role}


def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        user = db.query(User).filter(User.email == req.email.lower().strip()).first()
        client_ip = request.client.host if request and request.client else None

        if not user or not verify_password(req.password, user.hashed_password):
            # Log failed attempt - we don't know the user exists, try to find by email for logging
            failed_user = db.query(User).filter(User.email == req.email.lower().strip()).first()
            _log(
                db,
                user_id=failed_user.id if failed_user else None,
                action="login_failed",
                ip_address=client_ip,
                details={"reason": "invalid_password" if failed_user else "user_not_found"}
            )
            raise HTTPException(401, "Invalid email or password")
        if not user.is_active:
            # Log disabled account attempt
            _log(
                db,
                user_id=user.id,
                action="login_failed",
                ip_address=client_ip,
                details={"reason": "account_disabled"}
            )
            raise HTTPException(403, "Account disabled")

        payload = {"sub": str(user.id), "role": user.role, "tv": user.token_version}
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)

        # HttpOnly cookie storage (prevents JS access => mitigates XSS token theft)
        # max_age aligns with token expiry (seconds). Using simple conversion.
        access_max_age = 60 * get_settings().jwt_access_token_expire_minutes
        refresh_max_age = 60 * 60 * 24 * get_settings().jwt_refresh_token_expire_days

        set_jwt_cookie(response, "access_token", access_token, max_age=int(access_max_age))
        set_jwt_cookie(response, "refresh_token", refresh_token, max_age=int(refresh_max_age))

        user.last_login = datetime.utcnow()
        db.commit()
        _log(db, user.id, "login", ip_address=client_ip, details={"email": user.email, "role": str(user.role)})

        return {"role": user.role, "message": "Logged in"}

    except HTTPException:
        raise  # Re-raise HTTP exceptions (401, 403, etc.)
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.post("/register", status_code=201)
@limiter.limit("10 per minute")
def register_endpoint(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    return register(req, db)


@router.post("/login")
@limiter.limit("15 per minute")
def login_endpoint(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    return login(req, response, request, db)



@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Blacklist tokens in Redis to invalidate immediately
    from app.services.redis_service import get_redis_client
    redis_client = get_redis_client()
    for cookie_name in ("access_token", "refresh_token"):
        tok = request.cookies.get(cookie_name)
        if tok:
            try:
                payload = decode_token(tok)
                exp = payload.get("exp")
                if exp:
                    import time
                    remaining = int(exp - time.time())
                    if remaining > 0:
                        redis_client.set(f"jwt_blacklist:{tok}", "1", ex=remaining)
            except Exception:
                pass

    # Best-effort invalidation: bump token_version so current cookie becomes unusable.
    current_user.token_version += 1
    db.commit()

    clear_jwt_cookie(response, "access_token")
    clear_jwt_cookie(response, "refresh_token")

    _log(db, current_user.id, "logout")
    return {"message": "Logged out"}



@router.post("/refresh")

def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Missing refresh token")

    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Not a refresh token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(401, "User not found")

    new_payload = {"sub": str(user.id), "role": user.role, "tv": user.token_version}
    access_token = create_access_token(new_payload)

    access_max_age = 60 * get_settings().jwt_access_token_expire_minutes
    set_jwt_cookie(response, "access_token", access_token, max_age=int(access_max_age))

    return {"message": "Refreshed"}



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








