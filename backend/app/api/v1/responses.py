"""Response helpers shared by the version 1 API blueprints."""

from __future__ import annotations

from typing import Any

from flask import Response, jsonify, request


def _wants_pagination() -> bool:
    """Report whether the caller explicitly opted into a paginated envelope."""
    if "page" in request.args or "page_size" in request.args:
        return True
    flag = request.args.get("paginated")
    return flag is not None and flag.strip().lower() in {"1", "true", "yes", "on"}


def list_response(
    items: list[Any],
    *,
    total: int | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Response:
    """Return the bare JSON array the frontend expects.

    A paginated ``{"items", "page", "page_size", "total"}`` envelope is emitted
    only when the client explicitly asks for it with ``page``, ``page_size`` or
    ``paginated=true``. This keeps the React API wrappers simple while retaining
    an opt-in paginated representation for server-side consumers.
    """
    if not _wants_pagination():
        return jsonify(items)
    return jsonify(
        {
            "items": items,
            "page": page,
            "page_size": page_size if page_size is not None else len(items),
            "total": total if total is not None else len(items),
        }
    )
