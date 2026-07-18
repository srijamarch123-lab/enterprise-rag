from __future__ import annotations
from qdrant_client.models import Filter, FieldCondition, MatchAny, IsEmptyCondition, IsNullCondition, PayloadField


def build_rbac_filter(role: str) -> Filter:
    role = (role or "").strip().lower()
    if role.startswith("userrole."):
        clean_role = role.split(".")[-1]
    else:
        clean_role = role

    role_variants = [clean_role, f"UserRole.{clean_role}"]
    return Filter(
        should=[
            # Match points that have visible_roles set and contain the user's role
            FieldCondition(
                key="visible_roles",
                match=MatchAny(any=role_variants),
            ),
            # Also match points where visible_roles field is missing entirely (default public/internal)
            IsEmptyCondition(is_empty=PayloadField(key="visible_roles")),
            IsNullCondition(is_null=PayloadField(key="visible_roles")),
        ]
    )
