"""Creates a ready-to-use .env file (with a fresh random SECRET_KEY) if you do not have one.
Usage:  python setup_env.py            (local development settings)
        python setup_env.py --production
"""
import secrets, sys
from pathlib import Path

env = Path(__file__).parent / ".env"
if env.exists():
    sys.exit(".env already exists - nothing changed (delete it first if you want a new one).")
mode = "production" if "--production" in sys.argv else "development"
env.write_text(f"APP_ENV={mode}\nSECRET_KEY={secrets.token_hex(32)}\nPORT=5000\nDATABASE_PATH=app.db\nALLOWED_ORIGINS=\nAUTH_LIMIT=5\n")
print(f"Created .env ({mode} mode) with a new random SECRET_KEY. Keep this file private - it is git-ignored.")
