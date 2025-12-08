"""
IP Security Router - TASK-054
REST endpoints for IP-based security management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, IPvAnyAddress

from app.models import User
from app.dependencies import require_role
from app.services.ip_security import IPSecurityService

router = APIRouter()


class IPAddressRequest(BaseModel):
    ip_address: str
    reason: Optional[str] = None


class IPWhitelistEntry(BaseModel):
    ip_address: str
    added_by: Optional[str]
    added_at: Optional[str]


class IPBlacklistEntry(BaseModel):
    ip_address: str
    added_by: Optional[str]
    added_at: Optional[str]
    reason: Optional[str]


@router.get("/whitelist", response_model=List[IPWhitelistEntry])
async def get_whitelist(
    current_user: User = Depends(require_role(["admin"]))
):
    """Get all whitelisted IP addresses"""
    return IPSecurityService.get_whitelist()


@router.post("/whitelist")
async def add_to_whitelist(
    request: IPAddressRequest,
    current_user: User = Depends(require_role(["admin"]))
):
    """Add an IP address to the whitelist"""
    result = IPSecurityService.add_to_whitelist(
        request.ip_address, 
        added_by=current_user.email
    )
    return {
        "message": f"IP {request.ip_address} added to whitelist",
        "success": result
    }


@router.delete("/whitelist/{ip_address}")
async def remove_from_whitelist(
    ip_address: str,
    current_user: User = Depends(require_role(["admin"]))
):
    """Remove an IP address from the whitelist"""
    result = IPSecurityService.remove_from_whitelist(ip_address)
    if not result:
        raise HTTPException(status_code=404, detail="IP not found in whitelist")
    return {"message": f"IP {ip_address} removed from whitelist"}


@router.get("/blacklist", response_model=List[IPBlacklistEntry])
async def get_blacklist(
    current_user: User = Depends(require_role(["admin"]))
):
    """Get all blacklisted IP addresses"""
    return IPSecurityService.get_blacklist()


@router.post("/blacklist")
async def add_to_blacklist(
    request: IPAddressRequest,
    current_user: User = Depends(require_role(["admin"]))
):
    """Add an IP address to the blacklist"""
    result = IPSecurityService.add_to_blacklist(
        request.ip_address,
        reason=request.reason,
        added_by=current_user.email
    )
    return {
        "message": f"IP {request.ip_address} added to blacklist",
        "success": result
    }


@router.delete("/blacklist/{ip_address}")
async def remove_from_blacklist(
    ip_address: str,
    current_user: User = Depends(require_role(["admin"]))
):
    """Remove an IP address from the blacklist"""
    result = IPSecurityService.remove_from_blacklist(ip_address)
    if not result:
        raise HTTPException(status_code=404, detail="IP not found in blacklist")
    return {"message": f"IP {ip_address} removed from blacklist"}


@router.get("/suspicious")
async def get_suspicious_ips(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(["admin"]))
):
    """Get list of suspicious IP addresses for review"""
    return IPSecurityService.get_suspicious_ips(limit)


@router.get("/login-history/{email}")
async def get_login_history(
    email: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role(["admin", "manager"]))
):
    """Get login history for a specific user"""
    return IPSecurityService.get_login_history(email, limit)


@router.get("/check/{ip_address}")
async def check_ip_status(
    ip_address: str,
    current_user: User = Depends(require_role(["admin"]))
):
    """Check the status of an IP address"""
    return {
        "ip_address": ip_address,
        "is_blocked": IPSecurityService.is_ip_blocked(ip_address),
        "is_whitelisted": IPSecurityService.is_ip_whitelisted(ip_address),
        "failed_attempts": IPSecurityService.get_failed_attempts(ip_address)
    }


@router.post("/clear-attempts/{ip_address}")
async def clear_failed_attempts(
    ip_address: str,
    current_user: User = Depends(require_role(["admin"]))
):
    """Clear failed login attempts for an IP address"""
    result = IPSecurityService.clear_failed_attempts(ip_address)
    return {
        "message": f"Failed attempts cleared for {ip_address}",
        "success": result
    }


@router.get("/stats")
async def get_security_stats(
    current_user: User = Depends(require_role(["admin"]))
):
    """Get overall security statistics"""
    return IPSecurityService.get_security_stats()







