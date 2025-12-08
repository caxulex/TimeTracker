# 🔐 Security Remediation TODO List

**Created:** December 5, 2025  
**Target Completion:** Before Production Deployment  
**Goal:** Achieve 100% Secure Application (85+ Security Score)

---

## 📊 Progress Tracker

| Priority | Total | Completed | Remaining |
|----------|-------|-----------|-----------|
| 🔴 Critical | 4 | 0 | 4 |
| 🟠 High | 7 | 0 | 7 |
| 🟡 Medium | 8 | 0 | 8 |
| 🟢 Low | 4 | 0 | 4 |
| **Total** | **23** | **0** | **23** |

---

## 🔴 CRITICAL PRIORITY (Must Fix Immediately)

### SEC-001: Implement Secure Secret Management
**Vulnerability:** #1 - Hardcoded Secrets in Configuration  
**Effort:** Medium (4-6 hours)  
**Priority:** 🔴 Critical

#### Tasks:
- [ ] **SEC-001.1:** Generate cryptographically secure SECRET_KEY
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- [ ] **SEC-001.2:** Remove all default credentials from `config.py`
- [ ] **SEC-001.3:** Update `.env.example` with placeholder values only
- [ ] **SEC-001.4:** Add `.env` to `.gitignore` (verify not committed)
- [ ] **SEC-001.5:** Create `config.py` validation to reject default values
- [ ] **SEC-001.6:** Document secret generation in deployment guide

#### Implementation:
```python
# config.py - Add validation
class Settings(BaseSettings):
    SECRET_KEY: str
    
    @validator('SECRET_KEY')
    def validate_secret_key(cls, v):
        if v in ['your-super-secret-key-change-this-in-production', 
                 'time-tracker-secret-key-change-in-production-abc123xyz']:
            raise ValueError('Default SECRET_KEY detected. Generate a secure key!')
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters')
        return v
```

---

### SEC-002: Implement Token Blacklist on Logout
**Vulnerability:** #2 - JWT Token Not Blacklisted  
**Effort:** Medium (3-4 hours)  
**Priority:** 🔴 Critical

#### Tasks:
- [ ] **SEC-002.1:** Create Redis-based token blacklist service
- [ ] **SEC-002.2:** Add JTI (JWT ID) to token payload
- [ ] **SEC-002.3:** Store JTI in Redis on logout with TTL
- [ ] **SEC-002.4:** Check blacklist in `get_current_user` dependency
- [ ] **SEC-002.5:** Add token revocation API endpoint
- [ ] **SEC-002.6:** Write tests for token blacklist functionality

#### Implementation:
```python
# services/token_blacklist.py
import redis.asyncio as redis
from app.config import settings

class TokenBlacklist:
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL)
    
    async def blacklist_token(self, jti: str, expires_in: int):
        await self.redis.setex(f"blacklist:{jti}", expires_in, "1")
    
    async def is_blacklisted(self, jti: str) -> bool:
        return await self.redis.exists(f"blacklist:{jti}") > 0

# Update auth_service.py to include JTI
import uuid
def create_access_token(data: dict, ...):
    to_encode = data.copy()
    to_encode.update({"jti": str(uuid.uuid4()), ...})
```

---

### SEC-003: Implement Strong Password Policy
**Vulnerability:** #3 - Weak Password Requirements  
**Effort:** Medium (2-3 hours)  
**Priority:** 🔴 Critical

#### Tasks:
- [ ] **SEC-003.1:** Create password validation function
- [ ] **SEC-003.2:** Require minimum 12 characters
- [ ] **SEC-003.3:** Require uppercase, lowercase, number, special char
- [ ] **SEC-003.4:** Check against common password list (top 10,000)
- [ ] **SEC-003.5:** Add password strength indicator to frontend
- [ ] **SEC-003.6:** Update all password fields in schemas

#### Implementation:
```python
# utils/password_validator.py
import re

COMMON_PASSWORDS = set(open('common_passwords.txt').read().splitlines())

def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    errors = []
    
    if len(password) < 12:
        errors.append("Password must be at least 12 characters")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain lowercase letter")
    if not re.search(r'\d', password):
        errors.append("Password must contain a number")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain a special character")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common")
    
    return len(errors) == 0, errors
```

---

### SEC-004: Implement Rate Limiting
**Vulnerability:** #4 - No Rate Limiting  
**Effort:** Medium (3-4 hours)  
**Priority:** 🔴 Critical

#### Tasks:
- [ ] **SEC-004.1:** Install slowapi: `pip install slowapi`
- [ ] **SEC-004.2:** Configure rate limiter in main.py
- [ ] **SEC-004.3:** Add strict limits to auth endpoints (5/minute)
- [ ] **SEC-004.4:** Add general API limits (60/minute)
- [ ] **SEC-004.5:** Implement exponential backoff on failed logins
- [ ] **SEC-004.6:** Add rate limit headers to responses
- [ ] **SEC-004.7:** Write tests for rate limiting

#### Implementation:
```python
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# routers/auth.py
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

---

## 🟠 HIGH PRIORITY (Fix Before Production)

### SEC-005: Enforce HTTPS
**Vulnerability:** #5 - Missing HTTPS Enforcement  
**Effort:** Medium (2-3 hours)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-005.1:** Obtain SSL/TLS certificate (Let's Encrypt)
- [ ] **SEC-005.2:** Update nginx.conf for HTTPS
- [ ] **SEC-005.3:** Add HTTP to HTTPS redirect
- [ ] **SEC-005.4:** Add HSTS header
- [ ] **SEC-005.5:** Configure secure cookie settings
- [ ] **SEC-005.6:** Update CORS origins to HTTPS

#### Implementation:
```nginx
# nginx.conf
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    ...
}
```

---

### SEC-006: Secure Token Storage
**Vulnerability:** #6 - Tokens in localStorage  
**Effort:** High (6-8 hours)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-006.1:** Move refresh token to HttpOnly cookie
- [ ] **SEC-006.2:** Store access token in memory only (React context)
- [ ] **SEC-006.3:** Implement CSRF protection
- [ ] **SEC-006.4:** Update backend to set/read cookies
- [ ] **SEC-006.5:** Update frontend API client
- [ ] **SEC-006.6:** Handle token refresh via cookies
- [ ] **SEC-006.7:** Test cross-site scenarios

#### Implementation:
```python
# Backend: Set refresh token as cookie
from fastapi.responses import JSONResponse

@router.post("/login")
async def login(...):
    tokens = auth_service.create_tokens(user.id, user.email)
    response = JSONResponse({"access_token": tokens["access_token"]})
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    return response
```

---

### SEC-007: Add Content Security Policy
**Vulnerability:** #7 - Missing CSP Header  
**Effort:** Low (1-2 hours)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-007.1:** Define CSP policy for application
- [ ] **SEC-007.2:** Add CSP header to nginx.conf
- [ ] **SEC-007.3:** Test for CSP violations
- [ ] **SEC-007.4:** Set up CSP reporting endpoint
- [ ] **SEC-007.5:** Document CSP policy

#### Implementation:
```nginx
# nginx.conf
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' wss: https:; frame-ancestors 'self'; form-action 'self'; base-uri 'self';" always;
```

---

### SEC-008: Tighten CORS Configuration
**Vulnerability:** #8 - Overly Permissive CORS  
**Effort:** Low (1 hour)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-008.1:** Explicitly list allowed HTTP methods
- [ ] **SEC-008.2:** Explicitly list allowed headers
- [ ] **SEC-008.3:** Review and minimize ALLOWED_ORIGINS
- [ ] **SEC-008.4:** Remove localhost origins for production
- [ ] **SEC-008.5:** Test CORS preflight requests

#### Implementation:
```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Process-Time"],
    max_age=600,
)
```

---

### SEC-009: Disable Debug Mode for Production
**Vulnerability:** #9 - Debug Mode Enabled  
**Effort:** Low (30 minutes)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-009.1:** Set DEBUG=False in production .env
- [ ] **SEC-009.2:** Set ENVIRONMENT=production
- [ ] **SEC-009.3:** Verify TrustedHostMiddleware is enabled
- [ ] **SEC-009.4:** Verify error responses don't leak info
- [ ] **SEC-009.5:** Add production config validation

#### Implementation:
```python
# config.py
@validator('DEBUG')
def validate_debug_mode(cls, v, values):
    if values.get('ENVIRONMENT') == 'production' and v:
        raise ValueError('DEBUG must be False in production')
    return v
```

---

### SEC-010: Sanitize Error Responses
**Vulnerability:** #10 - Sensitive Data in Errors  
**Effort:** Medium (2-3 hours)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-010.1:** Create custom exception classes
- [ ] **SEC-010.2:** Implement centralized error handling
- [ ] **SEC-010.3:** Map internal errors to safe responses
- [ ] **SEC-010.4:** Log detailed errors server-side
- [ ] **SEC-010.5:** Return generic messages to clients
- [ ] **SEC-010.6:** Add request ID for error tracking

#### Implementation:
```python
# exceptions.py
class AppException(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status

# main.py
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    request_id = str(uuid.uuid4())
    logger.error(f"[{request_id}] {exc.code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status,
        content={"error": exc.code, "message": exc.message, "request_id": request_id}
    )
```

---

### SEC-011: Implement Account Lockout
**Vulnerability:** #11 - No Account Lockout  
**Effort:** Medium (3-4 hours)  
**Priority:** 🟠 High

#### Tasks:
- [ ] **SEC-011.1:** Create failed login attempt tracker (Redis)
- [ ] **SEC-011.2:** Lock account after 5 failed attempts
- [ ] **SEC-011.3:** Implement 15-minute lockout period
- [ ] **SEC-011.4:** Add unlock mechanism (admin/email)
- [ ] **SEC-011.5:** Send notification on lockout
- [ ] **SEC-011.6:** Log all lockout events
- [ ] **SEC-011.7:** Add CAPTCHA after 3 failures

#### Implementation:
```python
# services/login_security.py
class LoginSecurityService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.max_attempts = 5
        self.lockout_seconds = 900  # 15 minutes
    
    async def record_failed_attempt(self, email: str):
        key = f"login_attempts:{email}"
        attempts = await self.redis.incr(key)
        await self.redis.expire(key, self.lockout_seconds)
        return attempts >= self.max_attempts
    
    async def is_locked(self, email: str) -> bool:
        attempts = await self.redis.get(f"login_attempts:{email}")
        return int(attempts or 0) >= self.max_attempts
    
    async def clear_attempts(self, email: str):
        await self.redis.delete(f"login_attempts:{email}")
```

---

## 🟡 MEDIUM PRIORITY (Fix Soon)

### SEC-012: Secure Default Credentials
**Vulnerability:** #12 - Predictable Admin Credentials  
**Effort:** Medium (2-3 hours)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-012.1:** Remove default admin email from .env.example
- [ ] **SEC-012.2:** Generate random initial admin password
- [ ] **SEC-012.3:** Force password change on first login
- [ ] **SEC-012.4:** Create admin setup wizard
- [ ] **SEC-012.5:** Log admin account creation

---

### SEC-013: Secure WebSocket Authentication
**Vulnerability:** #13 - WebSocket Auth Bypass Risk  
**Effort:** Medium (3-4 hours)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-013.1:** Pass token in first WebSocket message (not URL)
- [ ] **SEC-013.2:** Implement periodic re-authentication
- [ ] **SEC-013.3:** Check user status on each message
- [ ] **SEC-013.4:** Add connection timeout (24 hours max)
- [ ] **SEC-013.5:** Close connection on user deactivation

---

### SEC-014: Sanitize Search Input
**Vulnerability:** #14 - LIKE Injection  
**Effort:** Low (1 hour)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-014.1:** Escape LIKE special characters (%, _)
- [ ] **SEC-014.2:** Limit search input length (100 chars)
- [ ] **SEC-014.3:** Validate search input format
- [ ] **SEC-014.4:** Add search rate limiting

#### Implementation:
```python
def sanitize_search(search: str, max_length: int = 100) -> str:
    if len(search) > max_length:
        search = search[:max_length]
    # Escape LIKE wildcards
    search = search.replace('%', r'\%').replace('_', r'\_')
    return search
```

---

### SEC-015: Implement Audit Logging
**Vulnerability:** #15 - No Audit Logging  
**Effort:** High (6-8 hours)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-015.1:** Create audit log model
- [ ] **SEC-015.2:** Create audit logging service
- [ ] **SEC-015.3:** Log authentication events
- [ ] **SEC-015.4:** Log admin operations
- [ ] **SEC-015.5:** Log data modifications
- [ ] **SEC-015.6:** Log access to sensitive data (payroll)
- [ ] **SEC-015.7:** Implement log retention policy
- [ ] **SEC-015.8:** Set up log monitoring/alerts

---

### SEC-016: Configure Password Hashing
**Vulnerability:** #16 - Unconfigured Hash Parameters  
**Effort:** Low (1 hour)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-016.1:** Configure bcrypt rounds (12 minimum)
- [ ] **SEC-016.2:** Add hash configuration to settings
- [ ] **SEC-016.3:** Document password storage approach
- [ ] **SEC-016.4:** Plan for future algorithm migration

---

### SEC-017: Implement Session Management
**Vulnerability:** #17 - Refresh Token Lifetime  
**Effort:** Medium (2-3 hours)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-017.1:** Implement sliding window refresh
- [ ] **SEC-017.2:** Add "remember me" functionality
- [ ] **SEC-017.3:** Reduce token lifetime for sensitive ops
- [ ] **SEC-017.4:** Implement absolute session timeout (30 days)

---

### SEC-018: Add Request Size Limits
**Vulnerability:** #18 - No Request Validation  
**Effort:** Low (1 hour)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-018.1:** Configure body size limit (10MB default)
- [ ] **SEC-018.2:** Add request timeout (30 seconds)
- [ ] **SEC-018.3:** Configure uvicorn limits
- [ ] **SEC-018.4:** Add file upload validation

---

### SEC-019: Restrict Payroll Data Access
**Vulnerability:** #19 - Broad Payroll Access  
**Effort:** Medium (3-4 hours)  
**Priority:** 🟡 Medium

#### Tasks:
- [ ] **SEC-019.1:** Create payroll_admin role
- [ ] **SEC-019.2:** Implement department-based access
- [ ] **SEC-019.3:** Add data masking for non-payroll admins
- [ ] **SEC-019.4:** Log all payroll data access

---

## 🟢 LOW PRIORITY (Enhance When Possible)

### SEC-020: Remove Server Information
**Vulnerability:** #20 - Server Information Disclosure  
**Effort:** Low (30 minutes)  
**Priority:** 🟢 Low

#### Tasks:
- [ ] **SEC-020.1:** Remove Server header in nginx
- [ ] **SEC-020.2:** Remove X-Powered-By header
- [ ] **SEC-020.3:** Customize error pages

---

### SEC-021: Add Security.txt
**Vulnerability:** #21 - Missing Security.txt  
**Effort:** Low (15 minutes)  
**Priority:** 🟢 Low

#### Tasks:
- [ ] **SEC-021.1:** Create security.txt file
- [ ] **SEC-021.2:** Define disclosure policy
- [ ] **SEC-021.3:** Add to /.well-known/ path

---

### SEC-022: Implement SRI
**Vulnerability:** #22 - No SRI for External Resources  
**Effort:** Low (30 minutes)  
**Priority:** 🟢 Low

#### Tasks:
- [ ] **SEC-022.1:** Audit external script/style resources
- [ ] **SEC-022.2:** Add integrity attributes
- [ ] **SEC-022.3:** Document SRI hashes

---

### SEC-023: Implement API Versioning
**Vulnerability:** #23 - No API Versioning  
**Effort:** Medium (2-3 hours)  
**Priority:** 🟢 Low

#### Tasks:
- [ ] **SEC-023.1:** Create /api/v1/ prefix structure
- [ ] **SEC-023.2:** Update all routes
- [ ] **SEC-023.3:** Document versioning strategy
- [ ] **SEC-023.4:** Plan deprecation process

---

## 📅 Implementation Schedule

### Week 1: Critical Items (SEC-001 to SEC-004)
| Day | Task | Estimated Hours |
|-----|------|-----------------|
| Mon | SEC-001: Secure Secrets | 5h |
| Tue | SEC-002: Token Blacklist | 4h |
| Wed | SEC-003: Password Policy | 3h |
| Thu | SEC-004: Rate Limiting | 4h |
| Fri | Testing & Validation | 4h |

### Week 2: High Priority Items (SEC-005 to SEC-011)
| Day | Task | Estimated Hours |
|-----|------|-----------------|
| Mon | SEC-005: HTTPS + SEC-009: Debug Mode | 3h |
| Tue | SEC-006: Secure Token Storage | 7h |
| Wed | SEC-007: CSP + SEC-008: CORS | 3h |
| Thu | SEC-010: Error Handling | 3h |
| Fri | SEC-011: Account Lockout | 4h |

### Week 3: Medium & Low Priority (SEC-012 to SEC-023)
| Day | Task | Estimated Hours |
|-----|------|-----------------|
| Mon | SEC-012, SEC-013: Credentials & WebSocket | 5h |
| Tue | SEC-014, SEC-015: Search & Audit Logging | 7h |
| Wed | SEC-016, SEC-017, SEC-018: Hash, Sessions, Limits | 4h |
| Thu | SEC-019, SEC-020, SEC-021: Payroll, Headers, Security.txt | 4h |
| Fri | SEC-022, SEC-023: SRI, Versioning + Final Testing | 3h |

---

## ✅ Verification Checklist

After completing all tasks, verify:

- [ ] All tests pass
- [ ] Security scan shows no critical issues
- [ ] Penetration testing completed
- [ ] OWASP ZAP scan clean
- [ ] Dependency audit clean
- [ ] Documentation updated
- [ ] Team security training complete

---

## 📚 Resources

- [OWASP Cheat Sheets](https://cheatsheetseries.owasp.org/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [React Security Best Practices](https://snyk.io/blog/10-react-security-best-practices/)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)

---

**Total Estimated Effort:** 60-70 hours  
**Recommended Timeline:** 3 weeks  
**Target Security Score:** 85+/100

---

*This TODO list should be tracked in your project management system and updated as items are completed.*
