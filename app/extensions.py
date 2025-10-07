from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# --- Supabase client (para Storage/Auth no backend) ---
import os
from supabase import create_client, Client

supabase: Client | None = None

def init_supabase() -> Client | None:
    """
    Inicializa o cliente Supabase usando SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.
    (SERVICE_ROLE deve ser usado só no backend.)
    """
    global supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        supabase = create_client(url, key)
    else:
        supabase = None
    return supabase
