from enum import Enum
import re


class InterestCategory(str, Enum):
    world = "World"
    sports = "Sports"
    business = "Business"
    science_technology = "Science/Technology"


class InteractionAction(str, Enum):
    viewed = "viewed"
    liked = "liked"
    skipped = "skipped"


class ErrorCode(str, Enum):
    # Auth — 401
    INVALID_CREDENTIALS = "invalid_credentials"
    TOKEN_INVALID = "token_invalid"
    TOKEN_EXPIRED = "token_expired"

    # Not found — 404
    USER_NOT_FOUND = "user_not_found"

    # Conflict — 409
    USERNAME_TAKEN = "username_taken"
    EMAIL_TAKEN = "email_taken"
    DUPLICATE_INTERACTION = "duplicate_interaction"

    # Validation — 422
    WEAK_PASSWORD = "weak_password"
    INVALID_USERNAME = "invalid_username"
    INVALID_EMAIL = "invalid_email"
    INVALID_INTERESTS = "invalid_interests"
    INVALID_ACTION = "invalid_action"
    VALIDATION_ERROR = "validation_error"

    # Service — 503
    NO_ARTICLES_INDEXED = "no_articles_indexed"

    # Internal — 500
    INTERNAL_ERROR = "internal_error"


# Disposable / fake email domains
BLOCKED_EMAIL_DOMAINS = {
    "example.com", "test.com", "fake.com",
    "mailinator.com", "tempmail.com", "guerrillamail.com",
    "yopmail.com", "throwam.com", "sharklasers.com",
}

# Popular domains — only exact match allowed
# e.g. gmail12.com, yahooo.com will be rejected
STRICT_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "icloud.com", "protonmail.com",
    "yahoo.in", "rediffmail.com",
}

# Email regex — allows + for aliasing, blocks special chars
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.+_-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
MAX_EMAIL_LENGTH = 254        # RFC 5321 standard max
MAX_EMAIL_LOCAL_LENGTH = 30   # characters before @

# Username
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 30

# Password
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72      # bcrypt hard limit
PASSWORD_UPPERCASE_REGEX = re.compile(r"[A-Z]")
PASSWORD_NUMBER_REGEX = re.compile(r"[0-9]")

# Interests
MIN_INTERESTS = 1
MAX_INTERESTS = 4