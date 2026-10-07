import reflex as rx
import os
from dotenv import load_dotenv

load_dotenv()

# Only use DATABASE_URL if it looks like a real URL (not the placeholder)
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url or "user:password@host" in _db_url or _db_url == "sqlite:///codementor.db":
    _db_url = "sqlite:///codementor.db"

_extra = {}
# Reflex Cloud injects the backend URL at deploy time; locally it defaults to
# http://localhost:8000. Set API_URL only to point a frontend at another backend.
if os.environ.get("API_URL"):
    _extra["api_url"] = os.environ["API_URL"]

config = rx.Config(
    app_name="codementor",
    db_url=_db_url,
    tailwind=None,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    **_extra,
)
