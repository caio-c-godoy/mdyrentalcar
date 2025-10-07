# scripts/init_db.py
"""
Cria as tabelas no banco apontado por DATABASE_URL (Supabase).
Uso (PowerShell no Windows):
  $env:DATABASE_URL = "postgresql+psycopg2://USER:PASS@HOST:6543/postgres?sslmode=require"
  python scripts/init_db.py
"""

import os, sys

# garante que o pacote do app seja encontrado
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# carrega o app (usa sua factory em wsgi.py)
from wsgi import app

# pega o db conforme tua estrutura (extensions.py)
from app.extensions import db  # type: ignore

def main():
    with app.app_context():
        # IMPORTANTE: importe os models antes do create_all
        import app.models  # noqa: F401

        db.create_all()
        print("✅ Tabelas criadas/atualizadas com sucesso no banco definido por DATABASE_URL.")

if __name__ == "__main__":
    main()
