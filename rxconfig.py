import reflex as rx
import os
from dotenv import load_dotenv

load_dotenv()

# Only use DATABASE_URL if it looks like a real URL (not the placeholder)
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url or "user:password@host" in _db_url or _db_url == "sqlite:///codementor.db":
    _db_url = "sqlite:///codementor.db"

config = rx.Config(
    app_name="codementor",
    db_url=_db_url,
    tailwind=None,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    # Backend URL for Reflex Cloud deployment
    api_url="https://be6df7dd-6c4d-4bb1-a59e-85c2dd171c63.fly.dev",
)
