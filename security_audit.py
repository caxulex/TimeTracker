"""
Automated Security Audit Script
Checks for common security issues in the Time Tracker application
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


class SecurityAuditor:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.issues: List[Tuple[str, str, str]] = []
        
    def audit(self):
        """Run all security checks"""
        print("🔒 Starting Security Audit...\n")
        
        self.check_secrets_in_code()
        self.check_sql_injection()
        self.check_hardcoded_credentials()
        self.check_debug_mode()
        self.check_unsafe_dependencies()
        self.check_cors_config()
        self.check_authentication()
        
        self.print_report()
        
    def check_secrets_in_code(self):
        """Check for hardcoded secrets"""
        print("📝 Checking for hardcoded secrets...")
        
        secret_patterns = [
            (r'password\s*=\s*["\'](?!.*\{)([^"\']{8,})["\']', "Hardcoded password"),
            (r'api[_-]?key\s*=\s*["\']([^"\']+)["\']', "Hardcoded API key"),
            (r'secret[_-]?key\s*=\s*["\'](?!.*SECRET)([^"\']+)["\']', "Hardcoded secret"),
            (r'token\s*=\s*["\']([a-zA-Z0-9]{20,})["\']', "Hardcoded token"),
        ]
        
        for py_file in self.base_path.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue
                
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                for pattern, issue_type in secret_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Exclude test files and example configs
                        if "test" not in str(py_file).lower() and "example" not in str(py_file).lower():
                            self.issues.append((
                                "HIGH",
                                issue_type,
                                f"{py_file}: {match.group(0)[:50]}..."
                            ))
        
        print("✅ Secret check complete\n")
    
    def check_sql_injection(self):
        """Check for potential SQL injection vulnerabilities"""
        print("📝 Checking for SQL injection risks...")
        
        sql_patterns = [
            r'execute\([f"].*{.*}',  # f-string in execute
            r'\.execute\(.*\+.*\)',   # String concatenation in execute
            r'SELECT.*%s.*FROM',      # Old-style string formatting
        ]
        
        for py_file in self.base_path.rglob("*.py"):
            if "venv" in str(py_file):
                continue
                
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                for pattern in sql_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        self.issues.append((
                            "CRITICAL",
                            "Potential SQL Injection",
                            f"{py_file}: Unsafe SQL query construction detected"
                        ))
        
        print("✅ SQL injection check complete\n")
    
    def check_hardcoded_credentials(self):
        """Check for hardcoded credentials in config"""
        print("📝 Checking for hardcoded credentials...")
        
        config_file = self.base_path / "backend" / "app" / "config.py"
        if config_file.exists():
            with open(config_file, 'r') as f:
                content = f.read()
                
                # Check if using environment variables
                if 'os.getenv' not in content and 'os.environ' not in content:
                    self.issues.append((
                        "MEDIUM",
                        "Config not using environment variables",
                        "config.py should use os.getenv() for secrets"
                    ))
        
        print("✅ Credentials check complete\n")
    
    def check_debug_mode(self):
        """Check if debug mode is enabled"""
        print("📝 Checking for debug mode...")
        
        for py_file in self.base_path.rglob("*.py"):
            if "venv" in str(py_file):
                continue
                
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                if re.search(r'debug\s*=\s*True', content, re.IGNORECASE):
                    if "main.py" in str(py_file):
                        self.issues.append((
                            "HIGH",
                            "Debug mode enabled",
                            f"{py_file}: Debug mode should be False in production"
                        ))
        
        print("✅ Debug mode check complete\n")
    
    def check_unsafe_dependencies(self):
        """Check requirements.txt for known vulnerable packages"""
        print("📝 Checking dependencies...")
        
        req_file = self.base_path / "backend" / "requirements.txt"
        if req_file.exists():
            print("   Run 'pip-audit' for detailed vulnerability scan")
        else:
            self.issues.append((
                "LOW",
                "Missing requirements.txt",
                "No requirements.txt found for dependency audit"
            ))
        
        print("✅ Dependency check complete\n")
    
    def check_cors_config(self):
        """Check CORS configuration"""
        print("📝 Checking CORS configuration...")
        
        main_file = self.base_path / "backend" / "app" / "main.py"
        if main_file.exists():
            with open(main_file, 'r') as f:
                content = f.read()
                
                # Check for wildcard origins
                if re.search(r'allow_origins\s*=\s*\["?\*"?\]', content):
                    self.issues.append((
                        "HIGH",
                        "CORS allows all origins",
                        "main.py: CORS should restrict origins in production"
                    ))
                
                # Check credentials with wildcard
                if '*' in content and 'allow_credentials=True' in content:
                    self.issues.append((
                        "CRITICAL",
                        "CORS misconfiguration",
                        "main.py: Cannot use wildcard origins with credentials"
                    ))
        
        print("✅ CORS check complete\n")
    
    def check_authentication(self):
        """Check authentication implementation"""
        print("📝 Checking authentication...")
        
        auth_file = self.base_path / "backend" / "app" / "services" / "auth.py"
        if auth_file.exists():
            with open(auth_file, 'r') as f:
                content = f.read()
                
                # Check for bcrypt usage
                if 'bcrypt' not in content:
                    self.issues.append((
                        "CRITICAL",
                        "Weak password hashing",
                        "auth.py: Should use bcrypt for password hashing"
                    ))
                
                # Check for JWT
                if 'jwt' not in content.lower():
                    self.issues.append((
                        "HIGH",
                        "Missing JWT implementation",
                        "auth.py: Should use JWT for token-based auth"
                    ))
        
        print("✅ Authentication check complete\n")
    
    def print_report(self):
        """Print security audit report"""
        print("\n" + "="*70)
        print("🔒 SECURITY AUDIT REPORT")
        print("="*70 + "\n")
        
        if not self.issues:
            print("✅ No security issues found! Great job!")
            return
        
        # Group by severity
        critical = [i for i in self.issues if i[0] == "CRITICAL"]
        high = [i for i in self.issues if i[0] == "HIGH"]
        medium = [i for i in self.issues if i[0] == "MEDIUM"]
        low = [i for i in self.issues if i[0] == "LOW"]
        
        print(f"🔴 CRITICAL: {len(critical)}")
        print(f"🟠 HIGH:     {len(high)}")
        print(f"🟡 MEDIUM:   {len(medium)}")
        print(f"🟢 LOW:      {len(low)}")
        print()
        
        if critical:
            print("\n🔴 CRITICAL ISSUES (Fix Immediately!):")
            print("-" * 70)
            for severity, issue, details in critical:
                print(f"  • {issue}")
                print(f"    {details}\n")
        
        if high:
            print("\n🟠 HIGH PRIORITY ISSUES:")
            print("-" * 70)
            for severity, issue, details in high:
                print(f"  • {issue}")
                print(f"    {details}\n")
        
        if medium:
            print("\n🟡 MEDIUM PRIORITY ISSUES:")
            print("-" * 70)
            for severity, issue, details in medium:
                print(f"  • {issue}")
                print(f"    {details}\n")
        
        if low:
            print("\n🟢 LOW PRIORITY ISSUES:")
            print("-" * 70)
            for severity, issue, details in low:
                print(f"  • {issue}")
                print(f"    {details}\n")
        
        print("\n" + "="*70)
        print(f"Total Issues: {len(self.issues)}")
        print("="*70)
        
        # Exit with error code if critical/high issues found
        if critical or high:
            sys.exit(1)


if __name__ == "__main__":
    base_path = Path(__file__).parent
    auditor = SecurityAuditor(str(base_path))
    auditor.audit()
