"""Append-only audit logging helper for F01-F08."""

from __future__ import annotations

from flask import request

from app.auth.permissions import current_actor
from app.errors import ApiError
from app.extensions import db
from app.models import AuditLog


def write_audit(
    action: str,
    resource: str,
    *,
    user_id: int | None = None,
) -> AuditLog:
    """Queue an audit row in the current transaction.

    Only the action name, a resource identifier, the actor id, the client IP
    and the server timestamp are stored. Callers must never pass request
    bodies, passwords or clinical content as ``action`` or ``resource``.
    The caller owns the transaction and must commit after a successful write.
    """
    clean_action = action.strip()[:50]
    clean_resource = resource.strip()[:100]
    if not clean_action or not clean_resource:
        raise ValueError("Audit action and resource must not be empty.")

    actor_id = user_id
    if actor_id is None:
        actor_id = current_actor().user_id
    if actor_id is None:
        raise ApiError(401, "login", "Authentication is required.")

    ip_address = request.remote_addr
    entry = AuditLog(
        user_id=actor_id,
        action=clean_action,
        resource=clean_resource,
        ip_address=ip_address[:45] if ip_address else None,
    )
    db.session.add(entry)
    return entry
