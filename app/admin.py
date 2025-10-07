from __future__ import annotations

import re
import time
from functools import wraps
from urllib.parse import quote
from .models import FaqItem
from app.extensions import supabase
import os
import uuid
import pathlib

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from .extensions import db
from sqlalchemy.exc import ProgrammingError, OperationalError
from .models import (
    FeaturedCategory,   # Usamos como "Carros"
    LegalPage,
    Location,
    QuoteRequest,
    SiteSetting,
)

# === Upload de imagens (serverless-friendly) ===
# Em Vercel, somente /tmp é gravável. Permite override via env: UPLOAD_DIR
TMP_ROOT = os.environ.get("TMPDIR") or "/tmp"
DEFAULT_UPLOAD_DIR = os.path.join(TMP_ROOT, "uploads")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", DEFAULT_UPLOAD_DIR)

try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except OSError:
    # Em teoria não deve falhar em /tmp; se falhar, ignora para não quebrar a função
    pass

ALLOWED_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def _save_uploaded_image(file_storage) -> str:
    """
    Função para salvar imagem, tentando enviar para o Supabase e, se falhar, salvando localmente.
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        print("UPLOAD→ Nenhum arquivo recebido!")
        return ""

    ext = pathlib.Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_IMG_EXTS:
        print(f"UPLOAD→ Extensão não permitida: {ext}")
        return ""

    unique = f"{uuid.uuid4().hex}{ext}"

    # Definir as chaves diretamente no código para teste
    SUPABASE_URL = 'https://btvfcbtaqddutipmhpkf.supabase.co'  # URL do Supabase
    SUPABASE_SERVICE_ROLE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ0dmZjYnRhcWRkdXRpcG1ocGtmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1OTg0Mjg4NSwiZXhwIjoyMDc1NDE4ODg1fQ.oX42yzGzMYOmi0BN1JpREvX3BTPc0z5YHIwQLpBfh1s'  # Exemplo de chave
    SUPABASE_BUCKET = 'mdy-uploads'  # Nome do bucket

    # Criando o cliente do Supabase com as variáveis definidas
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Expondo as variáveis para debugar
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {SUPABASE_SERVICE_ROLE_KEY}")
    print(f"SUPABASE_BUCKET: {SUPABASE_BUCKET}")

    # 1) Supabase (persistente)
    try:
        if supabase is not None and SUPABASE_BUCKET and SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
            path = f"categories/{secure_filename(unique)}"
            data = file_storage.read()

            print(f"UPLOAD→ Tentando fazer upload para o Supabase com o caminho: {path}")

            # Tenta fazer o upload
            file_opts = {
                "cache-control": "public, max-age=31536000",
                "content-type": file_storage.mimetype or "application/octet-stream",
                "contentType": file_storage.mimetype or "application/octet-stream",
            }

            # Envio para o Supabase
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=path,
                file=data,
                file_options=file_opts,
                upsert=True,  # Aqui fora!
            )
            # Verificando se o arquivo foi carregado corretamente
            public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)
            print(f"UPLOAD→ Sucesso! URL pública gerada: {public_url}")
            return public_url or ""
        else:
            print(
                "UPLOAD→ Erro: Supabase ou configuração do bucket está ausente."
                f" (supabase={supabase is not None}, bucket={SUPABASE_BUCKET}, url={'ok' if SUPABASE_URL else 'missing'}, role={'ok' if SUPABASE_SERVICE_ROLE_KEY else 'missing'})"
            )
    except Exception as e:
        print(f"UPLOAD→ Falha ao tentar fazer upload para o Supabase: {e!r}")
        return ""

    # 2) Fallback local (/tmp)
    try:
        upload_dir = current_app.config.get("UPLOAD_DIR")
        os.makedirs(upload_dir, exist_ok=True)
        dest = os.path.join(upload_dir, secure_filename(unique))
        file_storage.save(dest)
        print(f"UPLOAD→ Fallback: Arquivo salvo em /tmp: {dest}")
        return unique
    except Exception as e:
        print(f"UPLOAD→ Fallback falhou: {e!r}")
        return ""


# === fim upload ===


admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",  # Usa a pasta global app/templates
)


# ---------- Auth ----------
def check_auth(username: str | None, password: str | None) -> bool:
    return (
        username == current_app.config.get("ADMIN_USERNAME")
        and password == current_app.config.get("ADMIN_PASSWORD")
    )

def authenticate() -> Response:
    return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ---------- Helpers ----------
def _digits_only(n: str) -> str:
    return re.sub(r"\D+", "", n or "")

def _get_whatsapp_number_raw() -> str:
    # chave única usada no app
    return (SiteSetting.get_value("whatsapp_number", "") or "").strip()

# ---------- Home /admin ----------
@admin.get("/")
@requires_auth
def admin_home():
    # redireciona para a lista de categorias (carros)
    return redirect(url_for("admin.categories_list"))

# ---------- Configurações ----------
@admin.route("/settings", methods=["GET", "POST"])
@requires_auth
def settings():
    if request.method == "POST":
        whatsapp = (request.form.get("whatsapp") or "").strip()
        SiteSetting.set_value("whatsapp_number", whatsapp)
        flash("Configurações salvas.", "success")
        return redirect(url_for("admin.settings"))
    whatsapp = SiteSetting.get_value("whatsapp_number", "")
    return render_template("admin_settings.html", whatsapp=whatsapp)

# Exposição simples (se precisar no front)
@admin.get("/settings.json")
def settings_json():
    return jsonify({"whatsapp": _digits_only(_get_whatsapp_number_raw())})

@admin.get("/whatsapp")
def settings_whatsapp_plain():
    return _digits_only(_get_whatsapp_number_raw()), 200, {"Content-Type": "text/plain; charset=utf-8"}

# ---------- CATEGORIAS (Carros) ----------
@admin.get("/categories")
@requires_auth
def categories_list():
    cats = FeaturedCategory.query.order_by(
        FeaturedCategory.position.asc(),
        FeaturedCategory.id.asc()
    ).all()
    return render_template("admin_categories.html", categories=cats)

@admin.post("/categories/new")
@requires_auth
def categories_new():
    name = (request.form.get("name") or "").strip()
    slug = (request.form.get("slug") or "").strip().lower()
    pos = int(request.form.get("position") or 0)
    active = bool(request.form.get("active"))
    image_file = request.files.get("image_file")

    if not name or not slug:
        flash("Nome e slug são obrigatórios.", "danger")
        return redirect(url_for("admin.categories_list"))

    c = FeaturedCategory(name=name, slug=slug, position=pos, active=active)

    rel = _save_uploaded_image(image_file)
    if rel:
        # campo no modelo
        c.image_url = rel

    db.session.add(c)
    db.session.commit()
    flash("Categoria adicionada.", "success")
    return redirect(url_for("admin.categories_list"))

@admin.post("/categories/<int:cid>/toggle")
@requires_auth
def categories_toggle(cid: int):
    c = FeaturedCategory.query.get_or_404(cid)
    c.active = not c.active
    db.session.commit()
    return redirect(url_for("admin.categories_list"))

@admin.post("/categories/<int:cid>/delete")
@requires_auth
def categories_delete(cid: int):
    c = FeaturedCategory.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash("Categoria excluída.", "warning")
    return redirect(url_for("admin.categories_list"))

@admin.post("/categories/<int:cid>/update")
@requires_auth
def categories_update(cid: int):
    c = FeaturedCategory.query.get_or_404(cid)
    c.name = (request.form.get("name") or c.name).strip()
    c.slug = (request.form.get("slug") or c.slug).strip().lower()
    c.position = int(request.form.get("position") or c.position)
    c.active = bool(request.form.get("active")) if "active" in request.form else c.active

    image_file = request.files.get("image_file")
    rel = _save_uploaded_image(image_file)
    if rel:
        c.image_url = rel

    db.session.commit()
    flash("Categoria atualizada.", "success")
    return redirect(url_for("admin.categories_list"))
