"""F14 HL7 FHIR R4 endpoints backed by the ORM models."""

import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode

import simplejson
from flask import Blueprint, Response, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import current_actor, load_actor
from app.extensions import db as sqla_db
from app.fhir.resources import MAPPINGS
from app.fhir.writes import WRITERS
from app.models import CdssResult, ReviewStatus
from app.utils.common import ApiError, as_int, audit, body, clean_row, require_roles

fhir = Blueprint("fhir", __name__, url_prefix="/api/v1/fhir")
fhir.before_request(load_actor)
FHIR_JSON = "application/fhir+json"
ISSUE_TYPES = frozenset(
    {
        "invalid",
        "value",
        "login",
        "forbidden",
        "not-found",
        "not-supported",
        "conflict",
        "expired",
        "processing",
        "code-invalid",
        "duplicate",
        "too-long",
    }
)


def encode(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("Unexpected FHIR value.")


def fhir_json(
    payload: Any, status: int = 200, headers: dict[str, str] | None = None
) -> Response:
    data = simplejson.dumps(
        payload, default=encode, use_decimal=True, ensure_ascii=False
    )
    return Response(data, status=status, headers=headers, content_type=FHIR_JSON)


def fhir_error(status: int, code: str, message: str) -> Response:
    return fhir_json(
        {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": code if code in ISSUE_TYPES else "processing",
                    "diagnostics": message,
                }
            ],
        },
        status,
    )


def resource_url(kind: str, identity: Any) -> str:
    return url_for(
        "fhir.read_resource", kind=kind, identity=str(identity), _external=True
    )


@fhir.get("/metadata")
@require_roles("admin", "staff")
def metadata() -> Response:
    actor = current_actor()
    resources = []
    for kind, mapping in MAPPINGS.items():
        if actor.is_admin and mapping.clinical:
            continue
        interactions = ["read", "search-type"]
        if kind in WRITERS and actor.is_staff:
            interactions.append("create")
        search = [{"name": "_id", "type": "token"}]
        if mapping.patient_filter:
            search.append({"name": mapping.patient_filter, "type": "reference"})
        resources.append(
            {
                "type": kind,
                "interaction": [{"code": code} for code in interactions],
                "searchParam": search,
            }
        )
    return fhir_json(
        {
            "resourceType": "CapabilityStatement",
            "name": "OrthoPhaseTwoFHIR",
            "status": "active",
            "date": "2026-11-18",
            "kind": "instance",
            "fhirVersion": "4.0.1",
            "implementation": {
                "description": "Team 03 Phase 2 healthcare prototype",
                "url": request.base_url.removesuffix("/metadata"),
            },
            "format": [FHIR_JSON],
            "rest": [
                {
                    "mode": "server",
                    "security": {"description": "Bearer JWT required"},
                    "resource": resources,
                }
            ],
        }
    )


def mapped(kind: str) -> tuple[Any, Any]:
    mapping = MAPPINGS.get(kind)
    if mapping is None:
        raise ApiError(
            404,
            "not-supported",
            "This resource type is outside the available FHIR service.",
        )
    actor = current_actor()
    statement = mapping.query
    if actor.is_patient:
        if mapping.owner is None:
            raise ApiError(
                403, "forbidden", "This resource has no patient ownership scope."
            )
        statement = statement.where(mapping.owner == actor.patient_id)
        if kind == "DiagnosticReport":
            statement = statement.where(
                CdssResult.__table__.c.review_status == ReviewStatus.accepted
            )
    if actor.is_admin and mapping.clinical:
        raise ApiError(
            403,
            "forbidden",
            "Clinical resources are restricted to staff and their patients.",
        )
    return mapping, statement


def resource_json(kind: str, mapping: Any, row: Any, session: Any) -> dict[str, Any]:
    cleaned = clean_row(row)
    return {
        "resourceType": kind,
        "id": str(cleaned[mapping.identity.key]),
        **mapping.to_resource(cleaned, session),
    }


def logical_id(kind: str, identity: str) -> int | str:
    if kind == "Observation":
        if not re.fullmatch(r"[1-9][0-9]{0,9}-(pain|rom)", identity):
            raise ApiError(422, "value", "Supply a valid Observation id.")
        return identity
    return as_int(identity, "_id")


@fhir.get("/<kind>/<identity>")
def read_resource(kind: str, identity: str) -> Response:
    mapping, statement = mapped(kind)
    session = sqla_db.session
    row = (
        session.execute(statement.where(mapping.identity == logical_id(kind, identity)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "not-found", "Resource not found.")
    resource = resource_json(kind, mapping, row, session)
    if mapping.clinical:
        audit(session, "read", f"{kind}/{resource['id']}")
        session.commit()
    return fhir_json(resource)


@fhir.get("/<kind>")
def search(kind: str) -> Response:
    mapping, statement = mapped(kind)
    allowed = {"_id", "_count", "_page", "_format"}
    if mapping.patient_filter:
        allowed.add(mapping.patient_filter)
    invalid = set(request.args) - allowed
    if invalid or any(len(request.args.getlist(name)) > 1 for name in request.args):
        raise ApiError(
            400,
            "not-supported",
            "Use the search parameters listed in the capability statement.",
        )
    if "_id" in request.args:
        statement = statement.where(
            mapping.identity == logical_id(kind, request.args["_id"])
        )
    if mapping.patient_filter in request.args:
        raw = request.args[mapping.patient_filter]
        patient_id = as_int(raw.removeprefix("Patient/"), mapping.patient_filter)
        statement = statement.where(mapping.owner == patient_id)
    size = as_int(request.args.get("_count", "25"), "_count", maximum=100)
    page = as_int(request.args.get("_page", "1"), "_page", maximum=1_000_000)

    session = sqla_db.session
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (
        session.execute(
            statement.order_by(mapping.identity).limit(size).offset((page - 1) * size)
        )
        .mappings()
        .all()
    )
    entries = []
    for row in rows:
        resource = resource_json(kind, mapping, row, session)
        entries.append(
            {
                "fullUrl": resource_url(kind, resource["id"]),
                "resource": resource,
                "search": {"mode": "match"},
            }
        )
        if mapping.clinical:
            audit(session, "read", f"{kind}/{resource['id']}")
    if mapping.clinical and rows:
        session.commit()

    links = [{"relation": "self", "url": request.url}]
    if page * size < total:
        args: dict[str, Any] = request.args.to_dict()
        args["_page"] = page + 1
        links.append(
            {"relation": "next", "url": f"{request.base_url}?{urlencode(args)}"}
        )
    return fhir_json(
        {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": total,
            "link": links,
            "entry": entries,
        }
    )


@fhir.post("/<kind>")
@require_roles("staff")
def create(kind: str) -> Response:
    writer = WRITERS.get(kind)
    if writer is None:
        raise ApiError(
            405,
            "not-supported",
            "This resource does not support creation. Use /metadata.",
        )
    if request.mimetype not in ("application/json", FHIR_JSON):
        raise ApiError(415, "invalid", "Use application/fhir+json.")
    data = body()
    if data.get("resourceType") != kind:
        raise ApiError(422, "value", "resourceType must match the request path.")
    if "id" in data:
        raise ApiError(422, "value", "The server assigns resource IDs.")
    mapping = MAPPINGS[kind]
    session = sqla_db.session
    try:
        identity = writer(session, data)
        row = (
            session.execute(mapping.query.where(mapping.identity == identity))
            .mappings()
            .one()
        )
        resource = resource_json(kind, mapping, row, session)
        audit(session, "create", f"{kind}/{identity}")
        session.commit()
    except IntegrityError as error:
        session.rollback()
        state = getattr(error.orig, "sqlstate", None)
        if state == "23P01":
            raise ApiError(
                409,
                "conflict",
                "The practitioner already has a booking in this period.",
            ) from None
        if state == "23503":
            raise ApiError(
                422, "not-found", "A referenced record is unavailable."
            ) from None
        raise
    except Exception:
        session.rollback()
        raise
    return fhir_json(resource, 201, {"Location": resource_url(kind, resource["id"])})
