# app/__init__.py
from __future__ import annotations

import os
from flask import Flask

from .extensions import db
from .routes import site_bp
from .admin import admin
from . import models  # <- IMPORTANTE: garante que todos os models sejam registrados



def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    # Config: tenta via objeto informado na env; se falhar, usa defaults seguros
    cfg_obj = os.environ.get("FLASK_CONFIG_OBJECT", "app.config.Config")
    try:
        app.config.from_object(cfg_obj)
    except Exception:
        app.config.from_mapping(
            SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
            SQLALCHEMY_DATABASE_URI=os.environ.get(
                "DATABASE_URL",
                "postgresql+psycopg2://postgres:postgres@mdy_db:5432/postgres",
            ),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "admin"),
            ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin"),
        )

    # Extensões
    db.init_app(app)
    
    from app.extensions import init_supabase
    init_supabase()

# --- Uploads: em serverless só /tmp é gravável ---
    tmp_root = os.environ.get("TMPDIR") or "/tmp"
    app.config["UPLOAD_DIR"] = os.environ.get("UPLOAD_DIR", os.path.join(tmp_root, "uploads"))
    try:
        os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    except OSError:
        pass


    # Cria as tabelas na subida do app (inclui FaqItem etc.)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            # Evita travar o boot caso banco não esteja pronto ainda;
            # os logs do Gunicorn mostrarão o warning abaixo.
            app.logger.warning(f"db.create_all() falhou na inicialização: {e}")

    # Blueprints
    app.register_blueprint(site_bp)                      # público
    app.register_blueprint(admin, url_prefix="/admin")   # admin em /admin/*

    return app
