from fastapi import HTTPException, status
from app.core.constants import ErrorCode


class AppException(HTTPException):
    def __init__(self, status_code: int, error_code: ErrorCode, message: str):
        super().__init__(
            status_code=status_code,
            detail={
                "code": error_code.value,
                "message": message,
                "status": status_code,
            },
        )


class InvalidCredentialsError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=ErrorCode.INVALID_CREDENTIALS,
            message="Incorrect username or password",
        )


class TokenInvalidError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=ErrorCode.TOKEN_INVALID,
            message="Invalid or expired token",
        )


class UserNotFoundError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.USER_NOT_FOUND,
            message="User not found",
        )


class UsernameAlreadyExistsError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.USERNAME_TAKEN,
            message="Username is already taken",
        )


class EmailAlreadyExistsError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.EMAIL_TAKEN,
            message="Email is already registered",
        )


class NoArticlesIndexedError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=ErrorCode.NO_ARTICLES_INDEXED,
            message="No articles indexed yet. Run the ingest script first.",
        )


class DuplicateInteractionError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.DUPLICATE_INTERACTION,
            message="Interaction already logged for this article",
        )


class InvalidActionError(AppException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.INVALID_ACTION,
            message="action must be: viewed | liked | skipped",
        )