from __future__ import annotations
from qdrant_client.models import Filter, FieldCondition, MatchAny, IsEmptyCondition, IsNullCondition, PayloadField


def build_rbac_filter(role: str) -> Filter:
    role = (role or "").strip().lower()
    # Both formats exist in payload: "employee" and "UserRole.employee"
    # Include both so old and new points are matched
    role_variants = [
        "admin", "hr", "manager", "employee",
        "UserRole.admin", "UserRole.hr", "UserRole.manager", "UserRole.employee",
    ]
    return Filter(
        should=[
            # Match points that have visible_roles set and contain any role
            FieldCondition(
                key="visible_roles",
                match=MatchAny(any=role_variants),
            ),
            # Also match points where visible_roles field is missing entirely
            IsEmptyCondition(is_empty=PayloadField(key="visible_roles")),
            IsNullCondition(is_null=PayloadField(key="visible_roles")),
        ]
    )
