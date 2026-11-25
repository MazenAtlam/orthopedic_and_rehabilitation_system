"""F08 rehabilitation treatment plans and session endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.v1.responses import list_response
from app.auth import (
    current_actor,
    load_actor,
    require_clinical_staff,
    require_patient_or_staff,
    write_audit,
)
from app.errors import ApiError, FieldError
from app.extensions import db
from app.models import (
    Appointment,
    Patient,
    RehabSession,
    TreatmentPlan,
    TreatmentPlanStatus,
)
from app.schemas import (
    ValidationError,
    as_choice,
    as_date,
    as_decimal,
    as_int,
    as_text,
    collect,
    pagination,
    require_object,
)

treatment_plans_bp = Blueprint(
    "treatment_plans", __name__, url_prefix="/treatment-plans"
)
treatment_plans_bp.before_request(load_actor)

PLAN_EDITABLE_FIELDS = frozenset({"goal", "status"})


def _serialize_plan(plan: TreatmentPlan) -> dict[str, Any]:
    """Return the public fields of a rehabilitation plan."""
    return {
        "plan_id": plan.plan_id,
        "patient_id": plan.patient_id,
        "staff_id": plan.staff_id,
        "title": plan.title,
        "goal": plan.goal,
        "start_date": plan.start_date.isoformat(),
        "end_date": plan.end_date.isoformat() if plan.end_date is not None else None,
        "status": plan.status.value,
    }


def _serialize_session(session: RehabSession) -> dict[str, Any]:
    """Return a rehab session with a JSON-safe range-of-motion value."""
    return {
        "session_id": session.session_id,
        "plan_id": session.plan_id,
        "appointment_id": session.appointment_id,
        "session_date": session.session_date.isoformat(),
        "exercises": session.exercises,
        "pain_score": session.pain_score,
        "range_of_motion": (
            float(session.range_of_motion)
            if session.range_of_motion is not None
            else None
        ),
        "notes": session.notes,
    }


def _get_plan(plan_id: int) -> TreatmentPlan:
    """Return a treatment plan or raise a 404 error."""
    plan = db.session.get(TreatmentPlan, plan_id)
    if plan is None:
        raise ApiError(404, "not_found", "The requested treatment plan was not found.")
    return plan


def _assert_plan_access(plan: TreatmentPlan) -> None:
    """Allow clinical staff or the owning patient to read a plan."""
    actor = current_actor()
    if actor.is_patient and actor.patient_id != plan.patient_id:
        raise ApiError(
            403, "forbidden", "You can only access your own treatment plans."
        )


def _staff_actor_id() -> int:
    """Return the authenticated clinician's staff id."""
    actor = current_actor()
    if not actor.is_staff or actor.staff_id is None:
        raise ApiError(403, "forbidden", "Clinical staff access is required.")
    return actor.staff_id


@treatment_plans_bp.get("")
@require_patient_or_staff()
def list_treatment_plans() -> Response:
    """List plans with filters; patients only see their own plans."""
    actor = current_actor()
    page, page_size = pagination(request.args)
    patient_filter = as_int(
        request.args.get("patient_id") or request.args.get("patient"),
        "patient",
        required=False,
    )
    staff_filter = as_int(
        request.args.get("staff_id") or request.args.get("staff"),
        "staff",
        required=False,
    )
    status_value = as_choice(
        request.args.get("status"), "status", TreatmentPlanStatus, required=False
    )
    start_from = as_date(request.args.get("start_from"), "start_from", required=False)
    start_to = as_date(request.args.get("start_to"), "start_to", required=False)

    if start_from is not None and start_to is not None and start_to < start_from:
        raise ValidationError(
            [
                FieldError(
                    "start_to",
                    "Must be on or after start_from.",
                    "out_of_range",
                )
            ]
        )

    filters: list[Any] = []
    if actor.is_patient:
        if patient_filter is not None and patient_filter != actor.patient_id:
            raise ApiError(
                403, "forbidden", "You can only access your own treatment plans."
            )
        filters.append(TreatmentPlan.patient_id == actor.patient_id)
    elif patient_filter is not None:
        filters.append(TreatmentPlan.patient_id == patient_filter)
    if staff_filter is not None:
        filters.append(TreatmentPlan.staff_id == staff_filter)
    if status_value is not None:
        filters.append(TreatmentPlan.status == TreatmentPlanStatus(status_value))
    if start_from is not None:
        filters.append(TreatmentPlan.start_date >= start_from)
    if start_to is not None:
        filters.append(TreatmentPlan.start_date <= start_to)

    total = (
        db.session.scalar(
            select(func.count()).select_from(TreatmentPlan).where(*filters)
        )
        or 0
    )
    plans = db.session.scalars(
        select(TreatmentPlan)
        .where(*filters)
        .order_by(TreatmentPlan.start_date.desc(), TreatmentPlan.plan_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    resource = (
        f"patient:{actor.patient_id}" if actor.is_patient else "treatment_plan:list"
    )
    write_audit("treatment_plans_viewed", resource)
    response = list_response(
        [_serialize_plan(plan) for plan in plans],
        total=total,
        page=page,
        page_size=page_size,
    )
    db.session.commit()
    return response


@treatment_plans_bp.post("")
@require_clinical_staff()
def create_treatment_plan() -> tuple[Response, int]:
    """Create a treatment plan owned by a patient and the requesting clinician."""
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []

    patient_id = collect(
        errors, lambda: as_int(payload.get("patient_id"), "patient_id")
    )
    title = collect(
        errors, lambda: as_text(payload.get("title"), "title", max_length=150)
    )
    goal = collect(
        errors,
        lambda: as_text(payload.get("goal"), "goal", max_length=5000, required=False),
    )
    start_date = collect(
        errors, lambda: as_date(payload.get("start_date"), "start_date")
    )
    end_date = collect(
        errors,
        lambda: as_date(payload.get("end_date"), "end_date", required=False),
    )
    status_value = collect(
        errors,
        lambda: as_choice(
            payload.get("status"), "status", TreatmentPlanStatus, required=False
        ),
    )

    if errors:
        raise ValidationError(errors)
    if patient_id is None or title is None or start_date is None:
        raise ValidationError(
            [FieldError("body", "Required plan fields are missing.", "required")]
        )
    if end_date is not None and end_date < start_date:
        raise ValidationError(
            [
                FieldError(
                    "end_date",
                    "Must be on or after start_date.",
                    "out_of_range",
                )
            ]
        )

    if db.session.get(Patient, patient_id) is None:
        raise ApiError(404, "not_found", "The requested patient was not found.")

    plan = TreatmentPlan(
        patient_id=patient_id,
        staff_id=_staff_actor_id(),
        title=title,
        goal=goal,
        start_date=start_date,
        end_date=end_date,
        status=TreatmentPlanStatus(status_value or TreatmentPlanStatus.active.value),
    )
    db.session.add(plan)
    db.session.flush()
    write_audit("treatment_plan_created", f"plan:{plan.plan_id}")
    response = jsonify(_serialize_plan(plan))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The plan conflicts with existing data."
        ) from exc
    return response, 201


@treatment_plans_bp.patch("/<int:plan_id>")
@require_clinical_staff()
def update_treatment_plan(plan_id: int) -> Response:
    """Update a plan's goal or status."""
    plan = _get_plan(plan_id)
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []
    values: dict[str, Any] = {}

    if not any(field in payload for field in PLAN_EDITABLE_FIELDS):
        errors.append(
            FieldError("body", "At least one editable field is required.", "required")
        )
    if "goal" in payload:
        values["goal"] = collect(
            errors,
            lambda: as_text(payload["goal"], "goal", max_length=5000, required=False),
        )
    if "status" in payload:
        status_value = collect(
            errors,
            lambda: as_choice(payload["status"], "status", TreatmentPlanStatus),
        )
        if status_value is not None:
            values["status"] = TreatmentPlanStatus(status_value)

    if errors:
        raise ValidationError(errors)

    for field, value in values.items():
        setattr(plan, field, value)
    write_audit("treatment_plan_updated", f"plan:{plan_id}")
    response = jsonify(_serialize_plan(plan))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The update conflicts with existing data."
        ) from exc
    return response


@treatment_plans_bp.post("/<int:plan_id>/sessions")
@require_clinical_staff()
def create_rehab_session(plan_id: int) -> tuple[Response, int]:
    """Log a measured rehabilitation session against an existing plan."""
    plan = _get_plan(plan_id)
    payload = require_object(request.get_json(silent=True))
    errors: list[FieldError] = []

    session_date = collect(
        errors,
        lambda: as_date(payload.get("session_date"), "session_date", required=False),
    )
    pain_score = collect(
        errors,
        lambda: as_int(
            payload.get("pain_score"),
            "pain_score",
            minimum=0,
            maximum=10,
            required=False,
        ),
    )
    range_of_motion = collect(
        errors,
        lambda: as_decimal(
            payload.get("range_of_motion"),
            "range_of_motion",
            minimum=Decimal("0"),
            maximum=Decimal("9999.99"),
            places=2,
            required=False,
        ),
    )
    exercises = collect(
        errors,
        lambda: as_text(
            payload.get("exercises"), "exercises", max_length=5000, required=False
        ),
    )
    notes = collect(
        errors,
        lambda: as_text(payload.get("notes"), "notes", max_length=5000, required=False),
    )
    appointment_id = collect(
        errors,
        lambda: as_int(payload.get("appointment_id"), "appointment_id", required=False),
    )

    if errors:
        raise ValidationError(errors)

    if appointment_id is not None:
        appointment = db.session.get(Appointment, appointment_id)
        if appointment is None:
            errors.append(
                FieldError("appointment_id", "Unknown appointment.", "not_found")
            )
        elif appointment.patient_id != plan.patient_id:
            errors.append(
                FieldError(
                    "appointment_id",
                    "Must belong to this plan's patient.",
                    "invalid",
                )
            )
        elif (
            db.session.scalar(
                select(RehabSession.session_id).where(
                    RehabSession.appointment_id == appointment_id
                )
            )
            is not None
        ):
            raise ApiError(
                409,
                "session_exists",
                "This appointment already has a rehabilitation session.",
            )
        if errors:
            raise ValidationError(errors)

    session = RehabSession(
        plan_id=plan_id,
        appointment_id=appointment_id,
        session_date=session_date or date.today(),
        exercises=exercises,
        pain_score=pain_score,
        range_of_motion=range_of_motion,
        notes=notes,
    )
    db.session.add(session)
    db.session.flush()
    write_audit("rehab_session_created", f"session:{session.session_id}")
    response = jsonify(_serialize_session(session))
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError(
            409, "conflict", "The session conflicts with existing data."
        ) from exc
    return response, 201


@treatment_plans_bp.get("/<int:plan_id>/sessions")
@require_patient_or_staff()
def list_rehab_sessions(plan_id: int) -> Response:
    """List a plan's sessions for clinical staff or the owning patient."""
    plan = _get_plan(plan_id)
    _assert_plan_access(plan)
    page, page_size = pagination(request.args)

    total = (
        db.session.scalar(
            select(func.count())
            .select_from(RehabSession)
            .where(RehabSession.plan_id == plan_id)
        )
        or 0
    )
    sessions = db.session.scalars(
        select(RehabSession)
        .where(RehabSession.plan_id == plan_id)
        .order_by(RehabSession.session_date.desc(), RehabSession.session_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    write_audit("rehab_sessions_viewed", f"plan:{plan_id}")
    response = list_response(
        [_serialize_session(session) for session in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )
    db.session.commit()
    return response
