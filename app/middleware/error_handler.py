import logging
import uuid
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.constants import ErrorCode
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# Map pydantic field names → error codes + human issues
FIELD_ERROR_MAP = {
    "password": (ErrorCode.WEAK_PASSWORD, "weak_password"),
    "username": (ErrorCode.INVALID_USERNAME, "invalid_format"),
    "email":    (ErrorCode.INVALID_EMAIL, "invalid_format"),
    "interests":(ErrorCode.INVALID_INTERESTS, "invalid_value"),
}


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4())[:8])


def _parse_validation_errors(exc: RequestValidationError):
    """
    Parse pydantic errors into structured details.
    Returns (error_code, details_list)
    """
    details = []
    error_code = ErrorCode.VALIDATION_ERROR

    for error in exc.errors():
        loc = error.get("loc", [])
        field = loc[-1] if loc else "unknown"
        message = error.get("msg", "Invalid value").replace("Value error, ", "")

        # Determine specific error code from field
        if str(field) in FIELD_ERROR_MAP:
            code, issue = FIELD_ERROR_MAP[str(field)]
            if error_code == ErrorCode.VALIDATION_ERROR:
                error_code = code
        else:
            issue = "invalid_value"

        details.append({
            "field": str(field),
            "issue": issue,
            "message": message,
        })

    return error_code, details


async def app_exception_handler(request: Request, exc: AppException):
    request_id = _get_request_id(request)
    logger.warning({
        "request_id": request_id,
        "event": "app_exception",
        "error_code": exc.detail["code"],
        "path": str(request.url.path),
    })
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "request_id": request_id,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = _get_request_id(request)
    error_code, details = _parse_validation_errors(exc)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": error_code.value,
                "message": "Validation failed",
                "status": 422,
                "details": details,
            },
            "request_id": request_id,
        },
    )


async def global_exception_handler(request: Request, exc: Exception):
    request_id = _get_request_id(request)
    logger.error({
        "request_id": request_id,
        "event": "unhandled_exception",
        "error": str(exc),
        "path": str(request.url.path),
        "method": request.method,
    }, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "An internal error occurred. Please try again later.",
                "status": 500,
            },
            "request_id": request_id,
        },
    )