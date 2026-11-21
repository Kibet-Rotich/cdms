"""RFC 7807 (problem+json) style error responses with a stable `code` field."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class DomainError(Exception):
    """Raise from services for business-rule failures. Rendered as problem+json."""

    def __init__(self, code, detail, http_status=status.HTTP_400_BAD_REQUEST, extra=None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http_status = http_status
        self.extra = extra or {}


def problem_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        body = {
            "type": f"about:blank#{exc.code}",
            "title": exc.code.replace("_", " ").capitalize(),
            "status": exc.http_status,
            "code": exc.code,
            "detail": exc.detail,
            **exc.extra,
        }
        return Response(body, status=exc.http_status)

    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    code = getattr(exc, "default_code", "error")
    if isinstance(data, dict) and "detail" in data and len(data) == 1:
        detail, errors = str(data["detail"]), None
    else:
        detail, errors = "Validation failed.", data
        code = "validation_error"
    body = {
        "type": f"about:blank#{code}",
        "title": str(code).replace("_", " ").capitalize(),
        "status": response.status_code,
        "code": str(code).upper(),
        "detail": detail,
    }
    if errors is not None:
        body["errors"] = errors
    response.data = body
    return response
