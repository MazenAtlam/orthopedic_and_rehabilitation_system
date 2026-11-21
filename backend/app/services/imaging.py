"""PostgreSQL write functions for the team PACS, CDSS and annotation adapters."""

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import simplejson
from sqlalchemy import Text, cast, literal, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Connection

from app.utils.common import ApiError, as_date, as_int, as_text, audit
from app.models.schema_v1 import (
    annotation,
    cdss_result,
    medical_record,
    patient,
    scan,
    staff,
    user,
)

UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
ANNOTATION_TYPES = ("arrow", "length", "angle", "note")


def staff_identity(connection: Connection, actor_user_id: int) -> int:
    identity = connection.scalar(
        select(staff.c.staff_id)
        .select_from(staff.join(user))
        .where(
            user.c.user_id == actor_user_id,
            user.c.is_active,
            user.c.role == "staff",
        )
    )
    if identity is None:
        raise ApiError(403, "forbidden", "An active staff account is required.")
    return int(identity)


def register_study(
    connection: Connection, actor_user_id: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    uploader = staff_identity(connection, actor_user_id)
    patient_id = as_int(payload.get("patient_id"), "patient_id")
    record_id = payload.get("record_id")
    if record_id is not None:
        record_id = as_int(record_id, "record_id")
        if (
            connection.scalar(
                select(medical_record.c.record_id).where(
                    medical_record.c.record_id == record_id,
                    medical_record.c.patient_id == patient_id,
                )
            )
            is None
        ):
            raise ApiError(
                422, "value", "The visit must belong to the selected patient."
            )
    elif (
        connection.scalar(
            select(patient.c.patient_id).where(patient.c.patient_id == patient_id)
        )
        is None
    ):
        raise ApiError(404, "not-found", "Patient not found.")

    study_uid = as_text(payload.get("study_uid"), "study_uid", maximum=64)
    if not UID.fullmatch(study_uid):
        raise ApiError(422, "value", "study_uid must be a DICOM UID.")
    study_date = payload.get("study_date")
    values = {
        "patient_id": patient_id,
        "record_id": record_id,
        "study_uid": study_uid,
        "orthanc_id": as_text(payload.get("orthanc_id"), "orthanc_id", maximum=64),
        "modality": as_text(
            payload.get("modality"), "modality", maximum=10, optional=True
        ),
        "body_part": as_text(
            payload.get("body_part"), "body_part", maximum=50, optional=True
        ),
        "study_date": (
            as_date(study_date, "study_date") if study_date is not None else None
        ),
    }
    row = (
        connection.execute(
            insert(scan)
            .values(
                **values,
                uploaded_by=uploader,
            )
            .on_conflict_do_nothing(index_elements=[scan.c.study_uid])
            .returning(scan)
        )
        .mappings()
        .one_or_none()
    )

    if row is not None:
        audit(
            connection,
            "imaging.study.register",
            f"scan/{row['scan_id']}",
            actor_user_id,
        )
        return dict(row)

    existing = (
        connection.execute(select(scan).where(scan.c.study_uid == study_uid))
        .mappings()
        .one()
    )
    if any(existing[key] != value for key, value in values.items()):
        raise ApiError(
            409,
            "conflict",
            "This DICOM study UID is already registered with different metadata.",
        )
    return dict(existing)


def existing_scan(connection: Connection, scan_id: int) -> int:
    scan_id = as_int(scan_id, "scan_id")
    if (
        connection.scalar(select(scan.c.scan_id).where(scan.c.scan_id == scan_id))
        is None
    ):
        raise ApiError(404, "not-found", "Study not found.")
    return scan_id


def record_cdss_result(
    connection: Connection, actor_user_id: int, scan_id: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    staff_identity(connection, actor_user_id)
    scan_id = existing_scan(connection, scan_id)
    confidence = payload.get("confidence")
    if confidence is not None:
        if (
            type(confidence) not in (int, float, Decimal)
            or (isinstance(confidence, Decimal) and not confidence.is_finite())
            or not 0 <= confidence <= 1
        ):
            raise ApiError(422, "value", "confidence must be a number from 0 to 1.")
        confidence = float(confidence)

    row = (
        connection.execute(
            cdss_result.insert()
            .values(
                scan_id=scan_id,
                model_version=as_text(
                    payload.get("model_version"), "model_version", maximum=50
                ),
                finding=as_text(
                    payload.get("finding"), "finding", maximum=150, optional=True
                ),
                confidence=confidence,
                report_text=as_text(
                    payload.get("report_text"),
                    "report_text",
                    maximum=10000,
                    optional=True,
                ),
                review_status="pending",
            )
            .returning(cdss_result)
        )
        .mappings()
        .one()
    )
    audit(
        connection,
        "imaging.result.record",
        f"cdss_result/{row['result_id']}",
        actor_user_id,
    )
    return dict(row)


def review_cdss_result(
    connection: Connection, actor_user_id: int, result_id: int, decision: str
) -> dict[str, Any]:
    reviewer = staff_identity(connection, actor_user_id)
    result_id = as_int(result_id, "result_id")
    if decision not in ("accepted", "rejected"):
        raise ApiError(422, "value", "decision must be accepted or rejected.")

    query = cdss_result.c.result_id == result_id
    row = (
        connection.execute(select(cdss_result).where(query).with_for_update())
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(404, "not-found", "Result not found.")
    if row["review_status"] == decision and row["reviewed_by"] == reviewer:
        return dict(row)
    if row["review_status"] != "pending":
        raise ApiError(409, "conflict", "This result has already been reviewed.")

    updated = (
        connection.execute(
            cdss_result.update()
            .where(query)
            .values(
                review_status=decision,
                reviewed_by=reviewer,
            )
            .returning(cdss_result)
        )
        .mappings()
        .one()
    )
    audit(
        connection,
        f"imaging.result.{decision}",
        f"cdss_result/{result_id}",
        actor_user_id,
    )
    return dict(updated)


def record_annotation(
    connection: Connection, actor_user_id: int, scan_id: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    author = staff_identity(connection, actor_user_id)
    scan_id = existing_scan(connection, scan_id)
    kind = payload.get("type")
    if kind not in ANNOTATION_TYPES:
        raise ApiError(422, "value", "type must be arrow, length, angle or note.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ApiError(422, "value", "data must be a JSON object.")
    try:
        encoded = simplejson.dumps(
            data, allow_nan=False, use_decimal=True, ensure_ascii=False
        )
        if len(encoded.encode("utf-8")) > 65536 or "\\u0000" in encoded:
            raise ValueError
    except (TypeError, ValueError, RecursionError):
        raise ApiError(
            422, "value", "data must contain valid JSON up to 64 KiB."
        ) from None

    row = (
        connection.execute(
            annotation.insert()
            .values(
                scan_id=scan_id,
                created_by=author,
                type=kind,
                data=cast(literal(encoded, type_=Text()), JSONB),
                note=as_text(payload.get("note"), "note", maximum=2000, optional=True),
            )
            .returning(annotation)
        )
        .mappings()
        .one()
    )
    audit(
        connection,
        "imaging.annotation.record",
        f"annotation/{row['annotation_id']}",
        actor_user_id,
    )
    return dict(row)
