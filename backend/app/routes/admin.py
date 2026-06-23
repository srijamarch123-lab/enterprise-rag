from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.rbac import require_admin
from app.models import User, UserRole
from app.services.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdateRequest(BaseModel):
    user_id: int
    role: UserRole


@router.get("/users", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
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


@router.put("/users/role", dependencies=[Depends(require_admin)])
def update_role(
    body: RoleUpdateRequest,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == body.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = body.role
    user.token_version += 1  # invalidate existing tokens
    db.commit()
    return {"message": f"Role updated to {body.role} for user {user.email}"}


@router.put("/users/{user_id}/disable", dependencies=[Depends(require_admin)])
def disable_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    user.token_version += 1
    db.commit()
    return {"message": f"User {user.email} disabled"}


@router.put("/users/{user_id}/enable", dependencies=[Depends(require_admin)])
def enable_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.token_version += 1
    db.commit()
    return {"message": f"User {user.email} enabled"}
