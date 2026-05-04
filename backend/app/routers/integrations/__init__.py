"""Integration routers (third-party services).

Re-exports the per-integration router modules so that
``from app.routers.integrations import basecamp`` works alongside the
flat ``app/routers/*.py`` modules.
"""

from app.routers.integrations import basecamp  # noqa: F401

__all__ = ["basecamp"]
