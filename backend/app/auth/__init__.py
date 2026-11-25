"""Authentication and role-based access control helpers."""

from app.auth.access import load_actor
from app.auth.audit import write_audit
from app.auth.permissions import (
    Actor,
    can_read_record,
    current_actor,
    require_admin,
    require_admin_or_staff,
    require_clinical_staff,
    require_ownership,
    require_patient,
    require_patient_access,
    require_patient_or_staff,
    require_patient_owner,
    require_roles,
    require_staff,
)
from app.auth.tokens import (
    claims_for,
    current_token_id,
    issue_access_token,
    issue_tokens,
    revoke_current_refresh_token,
)

__all__ = [
    "Actor",
    "can_read_record",
    "claims_for",
    "current_actor",
    "current_token_id",
    "issue_access_token",
    "issue_tokens",
    "load_actor",
    "require_admin",
    "require_admin_or_staff",
    "require_clinical_staff",
    "require_ownership",
    "require_patient",
    "require_patient_access",
    "require_patient_or_staff",
    "require_patient_owner",
    "require_roles",
    "require_staff",
    "revoke_current_refresh_token",
    "write_audit",
]
