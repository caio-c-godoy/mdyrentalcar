# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# --- Supabase client (opcional no backend) ---
import os
from typing import Any

supabase: Any = None

def init_supabase():
    """
    Inicializa o cliente Supabase se o pacote e as ENVs existirem.
    Em produção, use SUPABASE_SERVICE_ROLE_KEY apenas no backend.
    """
    global supabase
    try:
        from supabase import create_client  # import lazy p/ não quebrar se pacote não instalado
    except Exception:
        supabase = None
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        try:
            supabase = create_client(url, key)
        except Exception:
            supabase = None
    else:
        supabase = None
    return supabase
