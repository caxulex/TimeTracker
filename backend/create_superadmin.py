"""Deprecated shim - use ``python -m scripts.create_superadmin`` instead.

This file previously contained a duplicate bootstrap implementation with
hardcoded credentials. To eliminate the security risk it now delegates to
the canonical, env-driven script under ``backend/scripts/create_superadmin.py``.
"""

import os
import sys

# Allow ``python create_superadmin.py`` from the backend WORKDIR.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.create_superadmin import create_superadmin  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(create_superadmin())
