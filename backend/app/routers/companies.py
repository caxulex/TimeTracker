"""
Company/Tenant Management API Router
Handles company registration, management, and white-label configuration.
"""

from typing import Optional, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

from app.database import get_db
from app.models import User, Company, WhiteLabelConfig
from app.services.auth_service import AuthService
from app.dependencies import get_current_user
from app.utils.password_validator import validate_password_strength

router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class CompanyRegister(BaseModel):
    """Schema for registering a new company"""
    company_name: str = Field(..., min_length=2, max_length=255)
    company_slug: Optional[str] = Field(None, min_length=2, max_length=100)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    admin_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    
    @field_validator('company_slug')
    @classmethod
    def validate_slug(cls, v):
        if v is None:
            return v
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class CompanyResponse(BaseModel):
    """Schema for company response"""
    id: int
    name: str
    slug: str
    email: str
    phone: Optional[str]
    timezone: str
    subscription_tier: str
    status: str
    trial_ends_at: Optional[datetime]
    max_users: int
    max_projects: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class CompanyUpdate(BaseModel):
    """Schema for updating company"""
    name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None


class WhiteLabelConfigCreate(BaseModel):
    """Schema for creating white-label config"""
    app_name: str = Field(default="Time Tracker", max_length=100)
    company_name: str = Field(..., max_length=255)
    tagline: Optional[str] = Field(None, max_length=255)
    subdomain: Optional[str] = Field(None, max_length=100)
    custom_domain: Optional[str] = Field(None, max_length=255)
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str = Field(default="#2563eb", max_length=7)
    secondary_color: Optional[str] = Field(None, max_length=7)
    support_email: Optional[EmailStr] = None
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None
    show_powered_by: bool = True


class WhiteLabelConfigResponse(BaseModel):
    """Schema for white-label config response"""
    id: int
    company_id: int
    app_name: str
    company_name: str
    tagline: Optional[str]
    subdomain: Optional[str]
    custom_domain: Optional[str]
    logo_url: Optional[str]
    favicon_url: Optional[str]
    login_background_url: Optional[str]
    primary_color: str
    secondary_color: Optional[str]
    accent_color: Optional[str]
    support_email: Optional[str]
    support_url: Optional[str]
    terms_url: Optional[str]
    privacy_url: Optional[str]
    show_powered_by: bool
    
    class Config:
        from_attributes = True


class WhiteLabelConfigUpdate(BaseModel):
    """Schema for updating white-label config"""
    app_name: Optional[str] = None
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    subdomain: Optional[str] = None
    custom_domain: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    login_background_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    support_email: Optional[str] = None
    support_url: Optional[str] = None
    terms_url: Optional[str] = None
    privacy_url: Optional[str] = None
    show_powered_by: Optional[bool] = None


class LoginInfo(BaseModel):
    """Login information for a company"""
    company_name: str
    company_slug: str
    login_url: str
    admin_email: str
    branding: Optional[WhiteLabelConfigResponse] = None


# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_slug(name: str) -> str:
    """Generate URL-safe slug from company name"""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug


# ============================================
# ENDPOINTS
# ============================================

@router.post("/register", response_model=LoginInfo, status_code=status.HTTP_201_CREATED)
async def register_company(
    data: CompanyRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new company with admin user.
    Returns login information for the new company.
    """
    # Validate password strength
    is_valid, password_errors = validate_password_strength(data.admin_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password does not meet requirements: {', '.join(password_errors)}"
        )
    
    # Generate slug if not provided
    slug = data.company_slug or generate_slug(data.company_name)
    
    # Check if slug already exists
    result = await db.execute(select(Company).where(Company.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company slug '{slug}' is already taken"
        )
    
    # Check if admin email already exists
    result = await db.execute(select(User).where(User.email == data.admin_email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered"
        )
    
    # Create company with 14-day trial
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    company = Company(
        name=data.company_name,
        slug=slug,
        email=data.admin_email,
        phone=data.phone,
        subscription_tier="trial",
        status="trial",
        trial_ends_at=trial_end,
        max_users=10,  # Trial limits
        max_projects=20,
    )
    db.add(company)
    await db.flush()  # Get company ID
    
    # Create white-label config with defaults
    white_label = WhiteLabelConfig(
        company_id=company.id,
        app_name=f"{data.company_name} Time Tracker",
        company_name=data.company_name,
        subdomain=slug,
        support_email=data.admin_email,
    )
    db.add(white_label)
    
    # Create admin user
    admin_user = User(
        email=data.admin_email,
        password_hash=AuthService.hash_password(data.admin_password),
        name=data.admin_name,
        role="company_admin",
        company_id=company.id,
        is_active=True,
    )
    db.add(admin_user)
    
    await db.commit()
    await db.refresh(company)
    await db.refresh(white_label)
    
    # Build login URL (adjust based on your domain setup)
    base_url = "http://localhost:5173"  # Change in production
    login_url = f"{base_url}/login?company={slug}"
    
    return LoginInfo(
        company_name=company.name,
        company_slug=company.slug,
        login_url=login_url,
        admin_email=data.admin_email,
        branding=WhiteLabelConfigResponse.model_validate(white_label),
    )


@router.get("/by-slug/{slug}", response_model=CompanyResponse)
async def get_company_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get company by slug (public endpoint for login page)"""
    result = await db.execute(select(Company).where(Company.slug == slug))
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return company


@router.get("/branding/{slug}", response_model=WhiteLabelConfigResponse)
async def get_company_branding(
    slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get white-label branding config by company slug (public endpoint)"""
    result = await db.execute(
        select(WhiteLabelConfig)
        .join(Company)
        .where(Company.slug == slug)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company branding not found"
        )
    
    return config


@router.get("/branding/by-domain/{domain}", response_model=WhiteLabelConfigResponse)
async def get_branding_by_domain(
    domain: str,
    db: AsyncSession = Depends(get_db)
):
    """Get white-label branding by custom domain or subdomain"""
    # Check custom domain first
    result = await db.execute(
        select(WhiteLabelConfig).where(WhiteLabelConfig.custom_domain == domain)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        # Check subdomain
        result = await db.execute(
            select(WhiteLabelConfig).where(WhiteLabelConfig.subdomain == domain)
        )
        config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branding configuration not found"
        )
    
    return config


@router.get("/my-company", response_model=CompanyResponse)
async def get_my_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's company"""
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return company


@router.put("/my-company", response_model=CompanyResponse)
async def update_my_company(
    data: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's company (company_admin only)"""
    if current_user.role not in ["company_admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company admins can update company settings"
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Update fields
    if data.name is not None:
        company.name = data.name
    if data.phone is not None:
        company.phone = data.phone
    if data.timezone is not None:
        company.timezone = data.timezone
    
    await db.commit()
    await db.refresh(company)
    
    return company


@router.get("/my-company/branding", response_model=WhiteLabelConfigResponse)
async def get_my_company_branding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's company branding config"""
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(WhiteLabelConfig).where(WhiteLabelConfig.company_id == current_user.company_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branding configuration not found"
        )
    
    return config


@router.put("/my-company/branding", response_model=WhiteLabelConfigResponse)
async def update_my_company_branding(
    data: WhiteLabelConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's company branding (company_admin only)"""
    if current_user.role not in ["company_admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company admins can update branding"
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(WhiteLabelConfig).where(WhiteLabelConfig.company_id == current_user.company_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branding configuration not found"
        )
    
    # Check subdomain uniqueness if changing
    if data.subdomain and data.subdomain != config.subdomain:
        result = await db.execute(
            select(WhiteLabelConfig).where(WhiteLabelConfig.subdomain == data.subdomain)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subdomain is already taken"
            )
    
    # Check custom domain uniqueness if changing
    if data.custom_domain and data.custom_domain != config.custom_domain:
        result = await db.execute(
            select(WhiteLabelConfig).where(WhiteLabelConfig.custom_domain == data.custom_domain)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom domain is already in use"
            )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    
    return config


@router.get("/list", response_model=List[CompanyResponse])
async def list_companies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all companies (super_admin only)"""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can list all companies"
        )
    
    result = await db.execute(select(Company).order_by(Company.created_at.desc()))
    companies = result.scalars().all()
    
    return list(companies)


# ============================================
# EMAIL SETTINGS SCHEMAS
# ============================================

class EmailSettingsResponse(BaseModel):
    """Schema for email settings response"""
    email_enabled: bool
    smtp_server: Optional[str] = None
    smtp_port: int
    smtp_username: Optional[str] = None
    smtp_password_set: bool  # True if password exists, never expose actual
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: bool


class EmailSettingsUpdate(BaseModel):
    """Schema for updating email settings"""
    email_enabled: Optional[bool] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # Only when changing
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = None
    smtp_use_tls: Optional[bool] = None


class TestEmailRequest(BaseModel):
    """Schema for test email request"""
    recipient: EmailStr


class TestEmailResponse(BaseModel):
    """Schema for test email response"""
    success: bool
    message: str
    latency_ms: Optional[int] = None


# ============================================
# EMAIL SETTINGS ENDPOINTS
# ============================================

@router.get("/my-company/email-settings", response_model=EmailSettingsResponse)
async def get_email_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get company email/SMTP settings (admin only)"""
    if current_user.role not in ["company_admin", "admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access email settings"
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return EmailSettingsResponse(
        email_enabled=company.email_enabled,
        smtp_server=company.smtp_server,
        smtp_port=company.smtp_port,
        smtp_username=company.smtp_username,
        smtp_password_set=bool(company.smtp_password_encrypted),
        smtp_from_email=company.smtp_from_email,
        smtp_from_name=company.smtp_from_name,
        smtp_use_tls=company.smtp_use_tls,
    )


@router.put("/my-company/email-settings", response_model=EmailSettingsResponse)
async def update_email_settings(
    data: EmailSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update company email/SMTP settings (admin only)"""
    from app.services.encryption_service import EncryptionService
    
    if current_user.role not in ["company_admin", "admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update email settings"
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Update fields
    if data.email_enabled is not None:
        company.email_enabled = data.email_enabled
    if data.smtp_server is not None:
        company.smtp_server = data.smtp_server
    if data.smtp_port is not None:
        company.smtp_port = data.smtp_port
    if data.smtp_username is not None:
        company.smtp_username = data.smtp_username
    if data.smtp_from_email is not None:
        company.smtp_from_email = data.smtp_from_email
    if data.smtp_from_name is not None:
        company.smtp_from_name = data.smtp_from_name
    if data.smtp_use_tls is not None:
        company.smtp_use_tls = data.smtp_use_tls
    
    # Encrypt password if provided
    if data.smtp_password is not None:
        encryption_service = EncryptionService()
        try:
            company.smtp_password_encrypted = encryption_service.encrypt(data.smtp_password)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to encrypt password: {str(e)}"
            )
    
    await db.commit()
    await db.refresh(company)
    
    return EmailSettingsResponse(
        email_enabled=company.email_enabled,
        smtp_server=company.smtp_server,
        smtp_port=company.smtp_port,
        smtp_username=company.smtp_username,
        smtp_password_set=bool(company.smtp_password_encrypted),
        smtp_from_email=company.smtp_from_email,
        smtp_from_name=company.smtp_from_name,
        smtp_use_tls=company.smtp_use_tls,
    )


@router.post("/my-company/email-settings/test", response_model=TestEmailResponse)
async def test_email_settings(
    data: TestEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a test email using company SMTP settings"""
    import time
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.utils import formataddr
    from app.services.encryption_service import EncryptionService
    
    if current_user.role not in ["company_admin", "admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test email settings"
        )
    
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a company"
        )
    
    result = await db.execute(
        select(Company).where(Company.id == current_user.company_id)
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    # Check if SMTP is configured
    if not company.smtp_server or not company.smtp_username or not company.smtp_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP settings are not fully configured"
        )
    
    # Decrypt password
    encryption_service = EncryptionService()
    try:
        smtp_password = encryption_service.decrypt(company.smtp_password_encrypted)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt SMTP password"
        )
    
    # Prepare test email
    from_name = company.smtp_from_name or company.name
    from_email = company.smtp_from_email or company.smtp_username
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Test Email from {company.name}"
    msg['From'] = formataddr((from_name, from_email))
    msg['To'] = data.recipient
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">✅ Email Configuration Test</h1>
            <p>This is a test email from <strong>{company.name}</strong>.</p>
            <p>If you received this email, your SMTP settings are configured correctly!</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <p><strong>SMTP Server:</strong> {company.smtp_server}</p>
                <p><strong>Port:</strong> {company.smtp_port}</p>
                <p><strong>TLS:</strong> {'Enabled' if company.smtp_use_tls else 'Disabled'}</p>
            </div>
            <p style="color: #666; font-size: 14px;">Sent at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, 'html'))
    
    # Send email and measure latency
    start_time = time.time()
    try:
        with smtplib.SMTP(company.smtp_server, company.smtp_port) as server:
            if company.smtp_use_tls:
                server.starttls()
            server.login(company.smtp_username, smtp_password)
            server.sendmail(from_email, data.recipient, msg.as_string())
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return TestEmailResponse(
            success=True,
            message=f"Test email sent successfully to {data.recipient}",
            latency_ms=latency_ms,
        )
    
    except smtplib.SMTPAuthenticationError:
        return TestEmailResponse(
            success=False,
            message="Authentication failed. Check your SMTP username and password.",
        )
    except smtplib.SMTPConnectError:
        return TestEmailResponse(
            success=False,
            message=f"Failed to connect to {company.smtp_server}:{company.smtp_port}",
        )
    except smtplib.SMTPRecipientsRefused:
        return TestEmailResponse(
            success=False,
            message=f"Recipient {data.recipient} was rejected by the server",
        )
    except Exception as e:
        return TestEmailResponse(
            success=False,
            message=f"Failed to send email: {str(e)}",
        )

