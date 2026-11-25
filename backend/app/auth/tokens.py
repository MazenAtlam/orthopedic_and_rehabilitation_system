"""JWT issuance and revocation helpers for F01."""

from __future__ import annotations

from typing import Any

from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt

from app.extensions import revoke_current_token
from app.models import User


def claims_for(user: User) -> dict[str, Any]:
    """Build the small claim set needed by RBAC checks."""
    return {
        "role": user.role.value,
        "patient_id": user.patient_profile.patient_id if user.patient_profile else None,
        "staff_id": user.staff_profile.staff_id if user.staff_profile else None,
    }


def issue_access_token(identity: str, claims: dict[str, Any]) -> str:
    """Issue a fresh access token for an existing authenticated identity."""
    return str(create_access_token(identity=identity, additional_claims=claims))


def issue_tokens(user: User) -> tuple[str, str]:
    """Return an access token and a refresh token for an active account."""
    claims = claims_for(user)
    identity = str(user.user_id)
    return (
        create_access_token(identity=identity, additional_claims=claims),
        create_refresh_token(identity=identity, additional_claims=claims),
    )


def revoke_current_refresh_token() -> None:
    """Denylist the refresh token in the current request context."""
    revoke_current_token()


def current_token_id() -> str | None:
    """Return the ``jti`` of the token in the current request context."""
    jti = get_jwt().get("jti")
    return jti if isinstance(jti, str) else None
