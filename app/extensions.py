# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# --- Supabase client (opcional no backend) ---
import os
from typing import Any

supabase: Any = None

def init_supabase():
    global supabase
    try:
        from supabase import create_client
        import supabase as sup_pkg
        print("SUPABASE_PY_VERSION=", getattr(sup_pkg, "__version__", "unknown"))
    except Exception as e:
        print(f"SUPABASE_IMPORT_ERROR: {e!r}")
        supabase = None
        return None
    ...
    if url and key:
        try:
            supabase = create_client(url, key)
            print("SUPABASE_CLIENT=OK")
        except Exception as e:
            print(f"SUPABASE_CLIENT_ERROR: {e!r}")
            supabase = None
    else:
        print("SUPABASE_ENVS_MISSING", {"url": bool(url), "key": bool(key)})
        supabase = None