from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()

