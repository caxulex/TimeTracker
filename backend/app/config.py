"""
Application configuration using Pydantic settings
SEC-001, SEC-009, SEC-012: Secure Configuration with Validation
"""

import json
import secrets
from typing import List, Optional, Union
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator, BeforeValidator
from typing_extensions import Annotated


def parse_list_from_env(v: Union[str, List[str]]) -> List[str]:
    """Parse a list from environment variable - handles JSON array or comma-separated"""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        v = v.strip()
        if v.startswith('['):
            return json.loads(v)
        return [x.strip() for x in v.split(',') if x.strip()]
    return []


# Type for env-parsed lists
EnvList = Annotated[List[str], BeforeValidator(parse_list_from_env)]


# Known insecure default values to reject
INSECURE_SECRET_KEYS = {
    "your-super-secret-key-change-this-in-production",
    "time-tracker-secret-key-change-in-production-abc123xyz",
    "changeme",
    "secret",
    "password",
    "key",
}

INSECURE_PASSWORDS = {
    "admin123",
    "changeme123",
    "password123",
    "admin",
    "password",
    "changeme",
}


class Settings(BaseSettings):
    """Application settings with security validation"""
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    # Application
    APP_NAME: str = "Time Tracker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False  # SEC-009: Default to False for security
    TESTING: bool = False  # Set to True in test environments
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/time_tracker"
    DATABASE_URL_TEST: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/time_tracker_test"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT - SEC-001: No default secret key
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS - SEC-008: Explicit configuration
    ALLOWED_ORIGINS: EnvList = ["http://localhost:5173", "http://localhost:3000"]
    ALLOWED_HOSTS: EnvList = ["localhost", "127.0.0.1"]

    # Email (for future use)
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # Admin - SEC-012: No default credentials
    FIRST_SUPER_ADMIN_EMAIL: str = ""
    FIRST_SUPER_ADMIN_PASSWORD: str = ""

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # SEC-004: Rate Limiting Configuration
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE: int = 5

    # SEC-018: Request Size Limits
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_REQUEST_SIZE_MB: int = 10
    REQUEST_TIMEOUT_SECONDS: int = 30

    # SEC-016: Password Hashing Configuration
    BCRYPT_ROUNDS: int = 12
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # File Upload
    UPLOAD_DIR: str = "uploads/"

    # External APIs
    JIRA_BASE_URL: Optional[str] = None
    JIRA_EMAIL: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    ASANA_ACCESS_TOKEN: Optional[str] = None
    TRELLO_API_KEY: Optional[str] = None
    TRELLO_TOKEN: Optional[str] = None

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """SEC-001: Validate SECRET_KEY is secure"""
        # Generate secure key if empty (for development only)
        if not v:
            v = secrets.token_urlsafe(64)
        
        # Check for known insecure values
        if v.lower() in INSECURE_SECRET_KEYS or len(v) < 32:
            raise ValueError(
                'SECRET_KEY is insecure. Generate a secure key with: '
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v

    @field_validator('FIRST_SUPER_ADMIN_PASSWORD')
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        """SEC-012: Validate admin password is secure"""
        if v and v.lower() in INSECURE_PASSWORDS:
            raise ValueError(
                'FIRST_SUPER_ADMIN_PASSWORD is too weak. Use a strong password.'
            )
        return v

    @model_validator(mode='after')
    def validate_production_settings(self):
        """SEC-009: Ensure production has secure settings"""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError('DEBUG must be False in production')
            if self.SECRET_KEY in INSECURE_SECRET_KEYS:
                raise ValueError('SECRET_KEY must be changed in production')
            if 'localhost' in str(self.ALLOWED_ORIGINS):
                import logging
                logging.warning('ALLOWED_ORIGINS contains localhost in production')
        return self

    @field_validator('BCRYPT_ROUNDS')
    @classmethod
    def validate_bcrypt_rounds(cls, v: int) -> int:
        """SEC-016: Ensure sufficient bcrypt rounds"""
        if v < 10:
            raise ValueError('BCRYPT_ROUNDS must be at least 10 for security')
        if v > 15:
            raise ValueError('BCRYPT_ROUNDS above 15 may cause performance issues')
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
