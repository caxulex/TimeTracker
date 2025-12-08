"""
IP-Based Security Service - TASK-054
Handles login tracking, IP whitelist, and security alerts
"""

import redis
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass
from app.config import settings

# Redis connection
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# Keys
IP_WHITELIST_KEY = "ip_security:whitelist"
IP_BLACKLIST_KEY = "ip_security:blacklist"
LOGIN_ATTEMPTS_PREFIX = "ip_security:attempts:"
LOGIN_HISTORY_PREFIX = "ip_security:history:"
SUSPICIOUS_IPS_KEY = "ip_security:suspicious"


@dataclass
class LoginAttempt:
    ip_address: str
    user_email: str
    timestamp: str
    success: bool
    user_agent: Optional[str] = None
    location: Optional[str] = None


class IPSecurityService:
    """Service for IP-based security features"""
    
    MAX_ATTEMPTS = 5  # Max failed attempts before blocking
    BLOCK_DURATION = 30 * 60  # 30 minutes in seconds
    HISTORY_RETENTION = 30  # Days to keep login history
    
    @staticmethod
    def record_login_attempt(
        ip_address: str,
        user_email: str,
        success: bool,
        user_agent: Optional[str] = None
    ) -> Dict:
        """Record a login attempt for tracking"""
        attempt = {
            "ip_address": ip_address,
            "user_email": user_email,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "user_agent": user_agent
        }
        
        # Store in login history
        history_key = f"{LOGIN_HISTORY_PREFIX}{user_email}"
        redis_client.lpush(history_key, json.dumps(attempt))
        redis_client.ltrim(history_key, 0, 99)  # Keep last 100 attempts
        redis_client.expire(history_key, 86400 * IPSecurityService.HISTORY_RETENTION)
        
        if not success:
            # Track failed attempts by IP
            attempts_key = f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}"
            redis_client.incr(attempts_key)
            redis_client.expire(attempts_key, IPSecurityService.BLOCK_DURATION)
            
            # Check if should be blocked
            attempts = int(redis_client.get(attempts_key) or 0)
            if attempts >= IPSecurityService.MAX_ATTEMPTS:
                IPSecurityService.add_suspicious_ip(ip_address, "Too many failed login attempts")
        else:
            # Clear failed attempts on successful login
            redis_client.delete(f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}")
        
        return attempt
    
    @staticmethod
    def get_login_history(user_email: str, limit: int = 20) -> List[Dict]:
        """Get login history for a user"""
        history_key = f"{LOGIN_HISTORY_PREFIX}{user_email}"
        raw_history = redis_client.lrange(history_key, 0, limit - 1)
        return [json.loads(h) for h in raw_history]
    
    @staticmethod
    def is_ip_blocked(ip_address: str) -> bool:
        """Check if an IP is currently blocked"""
        # Check blacklist
        if redis_client.sismember(IP_BLACKLIST_KEY, ip_address):
            return True
        
        # Check failed attempts
        attempts_key = f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}"
        attempts = int(redis_client.get(attempts_key) or 0)
        return attempts >= IPSecurityService.MAX_ATTEMPTS
    
    @staticmethod
    def is_ip_whitelisted(ip_address: str) -> bool:
        """Check if an IP is whitelisted"""
        return redis_client.sismember(IP_WHITELIST_KEY, ip_address)
    
    @staticmethod
    def add_to_whitelist(ip_address: str, added_by: str = None) -> bool:
        """Add an IP to the whitelist"""
        result = redis_client.sadd(IP_WHITELIST_KEY, ip_address)
        if added_by:
            meta_key = f"{IP_WHITELIST_KEY}:meta:{ip_address}"
            redis_client.hset(meta_key, mapping={
                "added_by": added_by,
                "added_at": datetime.utcnow().isoformat()
            })
        return bool(result)
    
    @staticmethod
    def remove_from_whitelist(ip_address: str) -> bool:
        """Remove an IP from the whitelist"""
        redis_client.delete(f"{IP_WHITELIST_KEY}:meta:{ip_address}")
        return bool(redis_client.srem(IP_WHITELIST_KEY, ip_address))
    
    @staticmethod
    def get_whitelist() -> List[Dict]:
        """Get all whitelisted IPs with metadata"""
        ips = redis_client.smembers(IP_WHITELIST_KEY)
        result = []
        for ip in ips:
            meta_key = f"{IP_WHITELIST_KEY}:meta:{ip}"
            meta = redis_client.hgetall(meta_key) or {}
            result.append({
                "ip_address": ip,
                "added_by": meta.get("added_by"),
                "added_at": meta.get("added_at")
            })
        return result
    
    @staticmethod
    def add_to_blacklist(ip_address: str, reason: str = None, added_by: str = None) -> bool:
        """Add an IP to the blacklist"""
        result = redis_client.sadd(IP_BLACKLIST_KEY, ip_address)
        meta_key = f"{IP_BLACKLIST_KEY}:meta:{ip_address}"
        redis_client.hset(meta_key, mapping={
            "added_by": added_by or "system",
            "added_at": datetime.utcnow().isoformat(),
            "reason": reason or "Manual block"
        })
        return bool(result)
    
    @staticmethod
    def remove_from_blacklist(ip_address: str) -> bool:
        """Remove an IP from the blacklist"""
        redis_client.delete(f"{IP_BLACKLIST_KEY}:meta:{ip_address}")
        redis_client.delete(f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}")
        return bool(redis_client.srem(IP_BLACKLIST_KEY, ip_address))
    
    @staticmethod
    def get_blacklist() -> List[Dict]:
        """Get all blacklisted IPs with metadata"""
        ips = redis_client.smembers(IP_BLACKLIST_KEY)
        result = []
        for ip in ips:
            meta_key = f"{IP_BLACKLIST_KEY}:meta:{ip}"
            meta = redis_client.hgetall(meta_key) or {}
            result.append({
                "ip_address": ip,
                "added_by": meta.get("added_by"),
                "added_at": meta.get("added_at"),
                "reason": meta.get("reason")
            })
        return result
    
    @staticmethod
    def add_suspicious_ip(ip_address: str, reason: str):
        """Flag an IP as suspicious for review"""
        entry = {
            "ip_address": ip_address,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        redis_client.lpush(SUSPICIOUS_IPS_KEY, json.dumps(entry))
        redis_client.ltrim(SUSPICIOUS_IPS_KEY, 0, 999)  # Keep last 1000
    
    @staticmethod
    def get_suspicious_ips(limit: int = 50) -> List[Dict]:
        """Get list of suspicious IPs for review"""
        raw = redis_client.lrange(SUSPICIOUS_IPS_KEY, 0, limit - 1)
        return [json.loads(s) for s in raw]
    
    @staticmethod
    def get_failed_attempts(ip_address: str) -> int:
        """Get number of failed login attempts for an IP"""
        attempts_key = f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}"
        return int(redis_client.get(attempts_key) or 0)
    
    @staticmethod
    def clear_failed_attempts(ip_address: str) -> bool:
        """Clear failed login attempts for an IP"""
        return bool(redis_client.delete(f"{LOGIN_ATTEMPTS_PREFIX}{ip_address}"))
    
    @staticmethod
    def get_security_stats() -> Dict:
        """Get overall security statistics"""
        return {
            "whitelisted_ips": redis_client.scard(IP_WHITELIST_KEY),
            "blacklisted_ips": redis_client.scard(IP_BLACKLIST_KEY),
            "suspicious_events": redis_client.llen(SUSPICIOUS_IPS_KEY)
        }
