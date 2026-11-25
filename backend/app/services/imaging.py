"""PostgreSQL write functions for the team PACS, CDSS and annotation adapters."""

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import simplejson
from sqlalchemy import Text, cast, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Connection

from app.models import (
    Annotation,
    AnnotationType,
    CdssResult,
    MedicalRecord,
    Patient,
    ReviewStatus,
    Scan,
    Staff,
    User,
    UserRole,
)
from app.utils.common import ApiError, as_date, as_int, as_text, audit, clean_row

UID = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
ANNOTATION_TYPES = ("arrow", "length", "angle", "note")


def staff_identity(connection: Connection, actor_user_id: int) -> int:
    identity = connection.scalar(
        select(Staff.staff_id)
        .select_from(Staff)
        .join(User, Staff.user_id == User.user_id)
        .where(
            User.user_id == actor_user_id,
            User.is_active.is_(True),
            User.role == UserRole.staff,
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
                select(MedicalRecord.record_id).where(
                    MedicalRecord.record_id == record_id,
                    MedicalRecord.patient_id == patient_id,
                )
            )
            is None
        ):
            raise ApiError(
                422, "value", "The visit must belong to the selected patient."
            )
    elif (
        connection.scalar(
            select(Patient.patient_id).where(Patient.patient_id == patient_id)
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
            insert(Scan)
            .values(
                **values,
                uploaded_by=uploader,
            )
            .on_conflict_do_nothing(index_elements=[Scan.study_uid])
            .returning(Scan.__table__)
        )
        .mappings()
        .one_or_none()
    )

    if row is not None:
        cleaned = clean_row(row)
        audit(
            connection,
            "imaging.study.register",
            f"scan/{cleaned['scan_id']}",
            actor_user_id,
        )
        return cleaned

    existing = clean_row(
        connection.execute(select(Scan.__table__).where(Scan.study_uid == study_uid))
        .mappings()
        .one()
    )
    if any(existing[key] != value for key, value in values.items()):
        raise ApiError(
            409,
            "conflict",
            "This DICOM study UID is already registered with different metadata.",
        )
    return existing


def existing_scan(connection: Connection, scan_id: int) -> int:
    scan_id = as_int(scan_id, "scan_id")
    if connection.scalar(select(Scan.scan_id).where(Scan.scan_id == scan_id)) is None:
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

    row = clean_row(
        connection.execute(
            insert(CdssResult)
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
                review_status=ReviewStatus.pending,
            )
            .returning(CdssResult.__table__)
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
    return row


def review_cdss_result(
    connection: Connection, actor_user_id: int, result_id: int, decision: str
) -> dict[str, Any]:
    reviewer = staff_identity(connection, actor_user_id)
    result_id = as_int(result_id, "result_id")
    if decision not in ("accepted", "rejected"):
        raise ApiError(422, "value", "decision must be accepted or rejected.")

    query = CdssResult.result_id == result_id
    raw_row = (
        connection.execute(select(CdssResult.__table__).where(query).with_for_update())
        .mappings()
        .one_or_none()
    )
    if raw_row is None:
        raise ApiError(404, "not-found", "Result not found.")
    row = clean_row(raw_row)
    if row["review_status"] == decision and row["reviewed_by"] == reviewer:
        return row
    if row["review_status"] != "pending":
        raise ApiError(409, "conflict", "This result has already been reviewed.")

    updated = clean_row(
        connection.execute(
            update(CdssResult)
            .where(query)
            .values(
                review_status=ReviewStatus(decision),
                reviewed_by=reviewer,
            )
            .returning(CdssResult.__table__)
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
    return updated


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

    row = clean_row(
        connection.execute(
            insert(Annotation)
            .values(
                scan_id=scan_id,
                created_by=author,
                type=AnnotationType(kind),
                data=cast(literal(encoded, type_=Text()), JSONB),
                note=as_text(payload.get("note"), "note", maximum=2000, optional=True),
            )
            .returning(Annotation.__table__)
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
    return row
