from __future__ import annotations

from qdrant_client.models import Filter, FieldCondition, MatchAny


ROLE_ACCESS_MAP: dict[str, list[str]] = {
    # Matches embedder.py policy:
    # - public/internal -> admin, hr, manager, employee
    # - confidential -> admin, hr, manager
    # - restricted -> admin, hr
    # In this repo the payload stores role strings in `visible_roles`,
    # so filter uses `visible_roles` contains the user's role.
    "admin": ["public", "internal", "confidential", "restricted"],
    "hr": ["public", "internal", "confidential"],
    "manager": ["public", "internal", "confidential"],
    "employee": ["public", "internal"],
}


def build_rbac_filter(role: str) -> Filter:
    """Build Qdrant RBAC filter.

    IMPORTANT: This project indexes payload field `visible_roles` as a list
    of role strings ("admin"/"hr"/...). Therefore the filter must check
    for membership of the user's role in `visible_roles`.

    The suggested Phase 4.1 mapping is kept, but applied correctly to the
    current payload schema.
    """

    role = (role or "").strip().lower()
    allowed_levels = ROLE_ACCESS_MAP.get(role, ["public"])

    # Convert levels -> roles using the same mapping logic as embedder.py.
    # For this repo, `visible_roles` contains roles, not access levels.
    # So we translate access levels to roles.
    visible_roles: set[str] = set()
    for level in allowed_levels:
        if level in ("public", "internal"):
            visible_roles.update({"admin", "hr", "manager", "employee"})
        elif level == "confidential":
            visible_roles.update({"admin", "hr", "manager"})
        elif level == "restricted":
            visible_roles.update({"admin", "hr"})
        else:
            visible_roles.update({"admin", "hr", "manager", "employee"})

    if not visible_roles:
        visible_roles = {"employee", "manager", "hr", "admin"}

    return Filter(
        must=[
            FieldCondition(
                key="visible_roles",
                match=MatchAny(any=list(visible_roles)),
            )
        ]
    )

