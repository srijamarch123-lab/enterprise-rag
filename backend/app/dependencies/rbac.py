from fastapi import Depends, HTTPException, status

from app.models import User, UserRole
from app.services.auth import get_current_user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory to require one of the allowed roles.
    Uses JWT current user from app.services.auth.get_current_user.
    """

    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


require_admin = require_role(UserRole.admin)
require_manager_or_above = require_role(UserRole.admin, UserRole.manager)
require_hr_or_above = require_role(UserRole.admin, UserRole.hr)
