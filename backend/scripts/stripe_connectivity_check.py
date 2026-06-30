"""Read-only Stripe connectivity check.

This script verifies that STRIPE_SECRET_KEY can authenticate with Stripe by
calling a read-only endpoint. It does not create or mutate any Stripe objects.
"""

from __future__ import annotations

import sys
from pathlib import Path

import stripe

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings


def main() -> int:
    api_key = settings.STRIPE_SECRET_KEY.strip()
    if not api_key:
        print("STRIPE_SECRET_KEY is missing. Set it in your local backend .env and retry.")
        return 2

    stripe.api_key = api_key

    try:
        # Read-only auth smoke test.
        stripe.Balance.retrieve()
        print("Stripe auth OK")
        return 0
    except stripe.error.AuthenticationError:
        print("Stripe auth failed (401). Check STRIPE_SECRET_KEY.")
        return 1
    except stripe.error.StripeError as exc:
        print(f"Stripe API error: {exc.user_message or str(exc)}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
