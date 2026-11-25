"""Version 1 API blueprint composing Hussein's F01-F08 routes and health check."""

from flask import Blueprint, Response, jsonify

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from app.api.v1.appointments import appointments_bp  # noqa: E402
from app.api.v1.auth import auth_bp  # noqa: E402
from app.api.v1.patients import patients_bp  # noqa: E402
from app.api.v1.records import records_bp  # noqa: E402
from app.api.v1.staff import staff_bp  # noqa: E402
from app.api.v1.treatment_plans import treatment_plans_bp  # noqa: E402
from app.api.v1.users import users_bp  # noqa: E402

for _blueprint in (
    auth_bp,
    users_bp,
    patients_bp,
    staff_bp,
    appointments_bp,
    records_bp,
    treatment_plans_bp,
):
    api_v1.register_blueprint(_blueprint)


@api_v1.get("/health")
def health() -> tuple[Response, int]:
    """Report that the API process is accepting requests."""
    return jsonify({"status": "ok"}), 200


__all__ = ["api_v1"]
