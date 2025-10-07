# scripts/init_db.py
import os, sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from wsgi import app
except Exception as e:
    print(f"[init_db] Falhou ao importar wsgi.app: {e}")
    sys.exit(1)

try:
    from app.extensions import db
except Exception as e:
    print(f"[init_db] Falhou ao importar app.extensions.db: {e}")
    sys.exit(1)

def main():
    print("[init_db] DATABASE_URL =", os.environ.get("DATABASE_URL"))
    with app.app_context():
        # garanta que os models sejam importados
        try:
            import app.models  # noqa: F401
        except Exception as e:
            print(f"[init_db] Aviso: não consegui importar app.models: {e}")
        # valida conexão antes
        try:
            db.session.execute(db.text("select 1"))
            print("[init_db] Conexão OK")
        except Exception as e:
            print(f"[init_db] Conexão falhou: {e}")
            sys.exit(1)

        db.create_all()
        print("✅ Tabelas criadas/atualizadas com sucesso.")

if __name__ == "__main__":
    main()
