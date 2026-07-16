"""
JWT authentication + bcrypt password hashing.

Current scheme:
- Access JWT is stored in an HttpOnly cookie named `access_token`.
- Refresh JWT is stored in an HttpOnly cookie named `refresh_token`.
"""

import secrets
from datetime import datetime, timedelta

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database import get_db
from app.models import PasswordResetToken, User

settings = get_settings()


# --- Password hashing ---------------------------------------------------------

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# --- JWT helpers -------------------------------------------------------------

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload["type"] = "access"
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token")

    payload = decode_token(access_token)
    user_id_raw = payload.get("sub")
    user_id: int | None = int(user_id_raw) if user_id_raw is not None else None
    token_version: int = payload.get("tv", 0)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid access token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    if user.token_version != token_version:
        raise HTTPException(status_code=401, detail="Token invalidated - please log in again")

    return user


# --- RBAC helper -------------------------------------------------------------

def require_role(*roles: str):
    def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {roles}. Your role: {user.role}",
            )
        return user

    return _check


# --- Password reset ---------------------------------------------------------

def create_reset_token(user_id: int, db: Session) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    entry = PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        used=False,
    )
    db.add(entry)
    db.commit()
    return token


# --- Cookie utilities -------------------------------------------------------

def set_jwt_cookie(response: Response, name: str, token: str, *, max_age: int) -> None:
    import os
    is_prod_cookie = (
        os.environ.get("RENDER") == "true"
        or os.environ.get("RAILWAY_ENVIRONMENT") is not None
        or os.environ.get("RAILWAY_ENVIRONMENT_NAME") is not None
        or os.environ.get("RAILWAY_PUBLIC_DOMAIN") is not None
        or os.environ.get("RAILWAY_SERVICE_ID") is not None
    )
    response.set_cookie(
        key=name,
        value=token,
        httponly=True,
        secure=is_prod_cookie,
        samesite="none" if is_prod_cookie else "lax",
        path="/",
        max_age=max_age,
    )


def clear_jwt_cookie(response: Response, name: str) -> None:
    import os
    is_prod_cookie = (
        os.environ.get("RENDER") == "true"
        or os.environ.get("RAILWAY_ENVIRONMENT") is not None
        or os.environ.get("RAILWAY_ENVIRONMENT_NAME") is not None
        or os.environ.get("RAILWAY_PUBLIC_DOMAIN") is not None
        or os.environ.get("RAILWAY_SERVICE_ID") is not None
    )
    response.delete_cookie(
        key=name,
        path="/",
        samesite="none" if is_prod_cookie else "lax",
        secure=is_prod_cookie,
    )





