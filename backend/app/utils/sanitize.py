"""
Search Sanitization Utility
SEC-014: Input Sanitization for LIKE Queries
Prevents SQL LIKE injection attacks
"""

import re
from typing import Optional


def sanitize_search_input(
    search: str,
    max_length: int = 100,
    allow_wildcards: bool = False
) -> str:
    """
    Sanitize search input to prevent LIKE injection attacks.
    
    Args:
        search: Raw search input
        max_length: Maximum allowed length
        allow_wildcards: Whether to allow % and _ wildcards
    
    Returns:
        Sanitized search string
    """
    if not search:
        return ""
    
    # Truncate to max length
    search = search[:max_length]
    
    # Remove null bytes
    search = search.replace('\x00', '')
    
    if not allow_wildcards:
        # Escape LIKE special characters
        search = search.replace('\\', '\\\\')  # Escape backslash first
        search = search.replace('%', '\\%')
        search = search.replace('_', '\\_')
    
    # Remove control characters
    search = ''.join(char for char in search if ord(char) >= 32 or char in '\t\n')
    
    return search.strip()


def sanitize_identifier(identifier: str, max_length: int = 64) -> str:
    """
    Sanitize an identifier (table name, column name).
    Only allows alphanumeric characters and underscores.
    
    Args:
        identifier: Raw identifier
        max_length: Maximum allowed length
    
    Returns:
        Sanitized identifier
    """
    if not identifier:
        return ""
    
    # Only allow alphanumeric and underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    
    return sanitized[:max_length]


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Raw filename
        max_length: Maximum allowed length
    
    Returns:
        Sanitized filename
    """
    if not filename:
        return ""
    
    # Remove path separators and null bytes
    sanitized = filename.replace('/', '').replace('\\', '').replace('\x00', '')
    
    # Remove dangerous patterns
    sanitized = sanitized.replace('..', '')
    
    # Only allow safe characters
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', sanitized)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    return sanitized[:max_length] if sanitized else "unnamed"


def validate_email_format(email: str) -> bool:
    """
    Validate email format (basic validation).
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid format, False otherwise
    """
    if not email or len(email) > 254:
        return False
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_json_string(value: str) -> str:
    """
    Sanitize a string that will be included in JSON.
    Escapes special characters.
    
    Args:
        value: Raw string value
    
    Returns:
        JSON-safe string
    """
    if not value:
        return ""
    
    # Escape special JSON characters
    escapes = {
        '\\': '\\\\',
        '"': '\\"',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\b': '\\b',
        '\f': '\\f',
    }
    
    result = value
    for char, escape in escapes.items():
        result = result.replace(char, escape)
    
    return result


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Args:
        text: Raw text that might contain HTML
    
    Returns:
        HTML-escaped text
    """
    if not text:
        return ""
    
    escapes = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
    }
    
    result = text
    for char, escape in escapes.items():
        result = result.replace(char, escape)
    
    return result


def create_safe_like_pattern(
    search: str,
    position: str = "contains"
) -> str:
    """
    Create a safe LIKE pattern from user input.
    
    Args:
        search: Sanitized search string
        position: Where to match - 'contains', 'starts', 'ends', 'exact'
    
    Returns:
        LIKE pattern with appropriate wildcards
    """
    sanitized = sanitize_search_input(search)
    
    if not sanitized:
        return "%"
    
    if position == "contains":
        return f"%{sanitized}%"
    elif position == "starts":
        return f"{sanitized}%"
    elif position == "ends":
        return f"%{sanitized}"
    else:  # exact
        return sanitized
