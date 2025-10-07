from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# --- Supabase client (opcional no backend) ---
import os
from typing import Any
from supabase import create_client

supabase: Any = None

def init_supabase():
    """
    Inicializa o cliente Supabase se o pacote e as ENVs existirem.
    Em produção, use SUPABASE_SERVICE_ROLE_KEY apenas no backend.
    """
    global supabase
    try:
        url = os.getenv("SUPABASE_URL", "https://btvfcbtaqddutipmhpkf.supabase.co")  # Default URL, caso a variável não esteja presente
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ0dmZjYnRhcWRkdXRpcG1ocGtmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1OTg0Mjg4NSwiZXhwIjoyMDc1NDE4ODg1fQ.oX42yzGzMYOmi0BN1JpREvX3BTPc0z5YHIwQLpBfh1s")  # Default role key if it's missing
        bucket = os.getenv("SUPABASE_BUCKET", "mdy-uploads")  # Default bucket name

        # Exibir as variáveis de ambiente
        print(f"SUPABASE_URL: {url}")
        print(f"SUPABASE_SERVICE_ROLE_KEY: {key}")
        print(f"SUPABASE_BUCKET: {bucket}")

        if url and key:
            supabase = create_client(url, key)
        else:
            supabase = None
    except Exception as e:
        supabase = None
        print(f"Erro ao inicializar o cliente do Supabase: {e}")

    return supabase
