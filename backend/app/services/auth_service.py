"""
Authentication service for JWT token management
SEC-002, SEC-016, SEC-017: Enhanced with token blacklist and secure hashing
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
import uuid

from app.config import settings


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        SEC-016: Hash a password using bcrypt with configurable rounds
        """
        salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
        return bcrypt.hashpw(password.encode(), salt).decode()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        except Exception:
            return False

    @staticmethod
    def create_access_token(
        data: dict, 
        expires_delta: Optional[timedelta] = None,
        jti: Optional[str] = None
    ) -> str:
        """
        SEC-002: Create a JWT access token with JTI for blacklisting
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        # SEC-002: Add unique token identifier for blacklisting
        token_jti = jti or str(uuid.uuid4())
        
        to_encode.update({
            "exp": expire,
            "type": "access",
            "jti": token_jti,
            "iat": datetime.now(timezone.utc)
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: dict, 
        expires_delta: Optional[timedelta] = None,
        jti: Optional[str] = None
    ) -> str:
        """
        SEC-002: Create a JWT refresh token with JTI for blacklisting
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        
        # SEC-002: Add unique token identifier for blacklisting
        token_jti = jti or str(uuid.uuid4())
        
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "jti": token_jti,
            "iat": datetime.now(timezone.utc)
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError:
            return None

    @staticmethod
    def get_token_jti(token: str) -> Optional[str]:
        """Extract JTI from a token without full validation"""
        try:
            # Decode without verification to get JTI
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            return payload.get("jti")
        except JWTError:
            return None

    @staticmethod
    def get_token_expiry_seconds(token: str) -> int:
        """Get remaining seconds until token expires"""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            exp = payload.get("exp")
            if exp:
                remaining = exp - datetime.now(timezone.utc).timestamp()
                return max(0, int(remaining))
            return 0
        except JWTError:
            return 0

    @staticmethod
    def create_tokens(user_id: int, email: str) -> dict:
        """Create both access and refresh tokens with unique JTIs"""
        token_data = {"sub": str(user_id), "email": email}
        
        # Generate unique JTIs for both tokens
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())
        
        access_token = AuthService.create_access_token(token_data, jti=access_jti)
        refresh_token = AuthService.create_refresh_token(token_data, jti=refresh_jti)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "access_jti": access_jti,
            "refresh_jti": refresh_jti,
        }


auth_service = AuthService()
