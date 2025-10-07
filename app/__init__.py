from __future__ import annotations

import os
from flask import Flask
from .extensions import db
from .routes import site_bp
from .admin import admin
from . import models  # <- IMPORTANTE: garante que todos os models sejam registrados
from app.extensions import init_supabase

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")

    # Configuração do banco de dados
    cfg_obj = os.environ.get("FLASK_CONFIG_OBJECT", "app.config.Config")
    try:
        app.config.from_object(cfg_obj)
    except Exception:
        app.config.from_mapping(
            SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret"),
            SQLALCHEMY_DATABASE_URI=os.environ.get(
                "DATABASE_URL",
                "postgresql://postgres.btvfcbtaqddutipmhpkf:1q2w3e4r%21Q%40W%23E%24R@aws-1-us-east-2.pooler.supabase.com:6543/postgres"
            ),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "admin"),
            ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin"),
        )

    # Inicializando as extensões
    db.init_app(app)
    
    # Inicializa o cliente Supabase
    init_supabase()

    # Configurações de upload (usando /tmp para gravar no Vercel)
    tmp_root = os.environ.get("TMPDIR") or "/tmp"
    app.config["UPLOAD_DIR"] = os.environ.get("UPLOAD_DIR", os.path.join(tmp_root, "uploads"))
    try:
        os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    except OSError:
        pass

    # Criando as tabelas na inicialização do app
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"db.create_all() falhou na inicialização: {e}")

    # Registrando os blueprints
    app.register_blueprint(site_bp)  # público
    app.register_blueprint(admin, url_prefix="/admin")  # admin em /admin/*

    return app
