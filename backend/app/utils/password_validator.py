"""
Password Validation Utility
SEC-003: Strong Password Policy Implementation
"""

import re
from typing import Tuple, List

# Common passwords list (top 100 most common)
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "passw0rd", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123", "batman",
    "login", "admin", "admin123", "changeme", "changeme123", "welcome", "welcome1",
    "hello", "charlie", "donald", "password2", "qwerty123", "whatever", "freedom",
    "computer", "internet", "starwars", "princess", "cheese", "killer", "pepper",
    "joshua", "jessica", "jennifer", "hunter", "hockey", "george", "flower",
    "daniel", "cowboy", "chicken", "canada", "abcdef", "access", "1234",
    "12345", "1234567890", "111111", "222222", "333333", "444444", "555555",
    "666666", "777777", "888888", "999999", "000000", "aaaaaa", "abcdefg",
    "asdfgh", "zxcvbn", "qwertyuiop", "password!", "p@ssw0rd", "p@ssword",
    "pass123", "pass1234", "123abc", "abc1234", "test", "test123", "test1234",
    "temp", "temp123", "temporary", "guest", "guest123", "root", "root123",
    "administrator", "letmein123", "welcome123", "hello123", "secret", "secret123"
}


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength according to security best practices.
    
    Requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common passwords list
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Length check
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long")
    
    if len(password) > 128:
        errors.append("Password must not exceed 128 characters")
    
    # Uppercase check
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Lowercase check
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Digit check
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    # Special character check
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~]', password):
        errors.append("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>-_=+[]\\;'`~)")
    
    # Common password check
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common. Please choose a more unique password")
    
    # Sequential characters check (e.g., 123, abc)
    if has_sequential_chars(password):
        errors.append("Password should not contain sequential characters (e.g., 123, abc)")
    
    # Repeated characters check (e.g., aaa, 111)
    if has_repeated_chars(password):
        errors.append("Password should not contain more than 2 repeated characters in a row")
    
    return len(errors) == 0, errors


def has_sequential_chars(password: str, length: int = 4) -> bool:
    """Check for sequential characters (ascending or descending)"""
    password_lower = password.lower()
    
    for i in range(len(password_lower) - length + 1):
        substring = password_lower[i:i + length]
        
        # Check alphabetic sequence
        if substring.isalpha():
            ords = [ord(c) for c in substring]
            if all(ords[j] + 1 == ords[j + 1] for j in range(len(ords) - 1)):
                return True
            if all(ords[j] - 1 == ords[j + 1] for j in range(len(ords) - 1)):
                return True
        
        # Check numeric sequence
        if substring.isdigit():
            if all(int(substring[j]) + 1 == int(substring[j + 1]) for j in range(len(substring) - 1)):
                return True
            if all(int(substring[j]) - 1 == int(substring[j + 1]) for j in range(len(substring) - 1)):
                return True
    
    return False


def has_repeated_chars(password: str, max_repeat: int = 2) -> bool:
    """Check for repeated characters beyond the allowed limit"""
    if len(password) <= max_repeat:
        return False
    
    for i in range(len(password) - max_repeat):
        if len(set(password[i:i + max_repeat + 1])) == 1:
            return True
    
    return False


def calculate_password_strength(password: str) -> int:
    """
    Calculate a password strength score from 0-100.
    
    Returns:
        Integer score from 0 (weak) to 100 (strong)
    """
    score = 0
    
    # Length bonus (up to 30 points)
    length = len(password)
    if length >= 8:
        score += 10
    if length >= 12:
        score += 10
    if length >= 16:
        score += 10
    
    # Character diversity (up to 40 points)
    if re.search(r'[a-z]', password):
        score += 10
    if re.search(r'[A-Z]', password):
        score += 10
    if re.search(r'\d', password):
        score += 10
    if re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~]', password):
        score += 10
    
    # Uniqueness (up to 20 points)
    unique_chars = len(set(password))
    if unique_chars >= 6:
        score += 10
    if unique_chars >= 10:
        score += 10
    
    # Penalties
    if password.lower() in COMMON_PASSWORDS:
        score -= 50
    if has_sequential_chars(password):
        score -= 10
    if has_repeated_chars(password):
        score -= 10
    
    # Additional entropy bonus (up to 10 points)
    if length >= 12 and unique_chars >= 8:
        score += 10
    
    return max(0, min(100, score))


def get_password_strength_label(score: int) -> str:
    """Get a human-readable strength label from score"""
    if score < 25:
        return "Very Weak"
    elif score < 50:
        return "Weak"
    elif score < 75:
        return "Moderate"
    elif score < 90:
        return "Strong"
    else:
        return "Very Strong"
