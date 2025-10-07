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
    bucket = os.getenv("SUPABASE_BUCKET")
    url = os.getenv("SUPABASE_URL")
    role = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    print(f"SUPABASE_URL: {url}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {role}")
    print(f"SUPABASE_BUCKET: {bucket}")

    # 1) Supabase (persistente)
    try:
        if supabase is not None and bucket and url and role:
            path = f"categories/{secure_filename(unique)}"
            data = file_storage.read()

            # Tenta fazer o upload
            file_opts = {
                "cache-control": "public, max-age=31536000",
                "content-type": file_storage.mimetype or "application/octet-stream",
                "contentType": file_storage.mimetype or "application/octet-stream",
            }
            # Envio para o Supabase
            supabase.storage.from_(bucket).upload(
                path=path,
                file=data,
                file_options=file_opts,
                upsert=True,  # Aqui fora!
            )
            public_url = supabase.storage.from_(bucket).get_public_url(path)
            print(f"UPLOAD→ Sucesso! URL pública gerada: {public_url}")
            return public_url or ""
        else:
            print(
                "UPLOAD→ Erro: Supabase ou configuração do bucket está ausente."
                f" (supabase={supabase is not None}, bucket={bucket}, url={'ok' if url else 'missing'}, role={'ok' if role else 'missing'})"
            )
    except Exception as e:
        print(f"UPLOAD→ Falha ao tentar fazer upload para o Supabase: {e!r}")

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

# ---------- CRM ----------
@admin.get("/crm")
@requires_auth
def crm_page():
    rows = QuoteRequest.query.order_by(QuoteRequest.created_at.desc()).all()
    return render_template("crm_quotes.html", items=rows)

@admin.get("/crm/cotacoes")
@requires_auth
def crm_cotacoes():
    return crm_page()

# Link WhatsApp (cliente)
@admin.get("/crm/cotacoes/<int:qid>/whatsapp-link")
@requires_auth
def crm_cotacao_whatsapp_link(qid: int):
    r = QuoteRequest.query.get_or_404(qid)
    d = re.sub(r"\D+", "", r.phone or "")
    if d and not d.startswith("55") and len(d) in (10, 11):
        d = "55" + d
    msg = (
        f"Olá {(r.name or '').split()[0]}, tudo bem?\n\n"
        f"Recebemos sua solicitação de reserva na MDY. Seguem os detalhes:\n"
        f"• Retirada: {r.pickup_place} — {r.pickup_date or 'data a combinar'}\n"
        f"• Devolução: {r.drop_place} — {r.drop_date or 'data a combinar'}\n"
        f"• Categoria: {r.category}\n\n"
        f"Podemos dar sequência à sua reserva?"
    )
    url = f"https://wa.me/{d}?text={quote(msg, safe='')}" if d else f"https://wa.me/?text={quote(msg, safe='')}"
    return jsonify({"ok": True, "url": url})

@admin.get("/crm/cotacoes/<int:qid>/whatsapp")
@requires_auth
def crm_cotacao_whatsapp_redirect(qid: int):
    r = QuoteRequest.query.get_or_404(qid)
    d = re.sub(r"\D+", "", r.phone or "")
    if d and not d.startswith("55") and len(d) in (10, 11):
        d = "55" + d
    msg = (
        f"Olá {(r.name or '').split()[0]}, tudo bem?\n\n"
        f"Recebemos sua solicitação de reserva na MDY. Seguem os detalhes:\n"
        f"• Retirada: {r.pickup_place} — {r.pickup_date or 'data a combinar'}\n"
        f"• Devolução: {r.drop_place} — {r.drop_date or 'data a combinar'}\n"
        f"• Categoria: {r.category}\n\n"
        f"Podemos dar sequência à reserva?"
    )
    url = f"https://wa.me/{d}?text={quote(msg, safe='')}" if d else f"https://wa.me/?text={quote(msg, safe='')}"
    return redirect(url)

# ---------- Localidades ----------
@admin.get("/locations")
@requires_auth
def locations_list():
    rows = Location.query.order_by(Location.position.asc(), Location.name.asc()).all()
    return render_template("admin_locations.html", locations=rows)

@admin.post("/locations/new")
@requires_auth
def locations_new():
    name = (request.form.get("name") or "").strip()
    pos = int(request.form.get("position") or 0)
    if not name:
        flash("Nome é obrigatório.", "danger")
        return redirect(url_for("admin.locations_list"))
    existing = Location.query.filter_by(name=name).first()
    if existing:
        flash("Já existe uma localidade com esse nome.", "warning")
        return redirect(url_for("admin.locations_list"))
    db.session.add(Location(name=name, position=pos, active=True))
    db.session.commit()
    flash("Localidade adicionada.", "success")
    return redirect(url_for("admin.locations_list"))

@admin.post("/locations/<int:lid>/update")
@requires_auth
def locations_update(lid: int):
    loc = Location.query.get_or_404(lid)
    loc.name = (request.form.get("name") or loc.name).strip()
    loc.position = int(request.form.get("position") or loc.position)
    db.session.commit()
    flash("Localidade atualizada.", "success")
    return redirect(url_for("admin.locations_list"))

@admin.post("/locations/<int:lid>/toggle")
@requires_auth
def locations_toggle(lid: int):
    loc = Location.query.get_or_404(lid)
    loc.active = not loc.active
    db.session.commit()
    return redirect(url_for("admin.locations_list"))

@admin.post("/locations/<int:lid>/delete")
@requires_auth
def locations_delete(lid: int):
    loc = Location.query.get_or_404(lid)
    db.session.delete(loc)
    db.session.commit()
    flash("Localidade excluída.", "warning")
    return redirect(url_for("admin.locations_list"))

# ---------- Páginas legais ----------
@admin.get("/legal")
@requires_auth
def admin_legal_get():
    privacy = LegalPage.get_or_create("privacy", "Política de Privacidade")
    terms = LegalPage.get_or_create("terms", "Termos de Uso")
    return render_template("admin_legal.html", privacy=privacy, terms=terms)

@admin.post("/legal")
@requires_auth
def admin_legal_post():
    privacy_html = request.form.get("privacy_html", "")
    terms_html = request.form.get("terms_html", "")
    privacy = LegalPage.get_or_create("privacy", "Política de Privacidade")
    terms = LegalPage.get_or_create("terms", "Termos de Uso")
    privacy.html = privacy_html
    terms.html = terms_html
    db.session.commit()
    flash("Páginas salvas.", "success")
    return redirect(url_for("admin.admin_legal_get"))

@admin.route("/legal/<key>", methods=["GET", "POST"])
@requires_auth
def admin_legal_edit(key):
    if key not in ("privacy", "terms"):
        flash("Página inválida.", "danger")
        return redirect(url_for("admin.admin_legal_get"))

    default_title = "Política de Privacidade" if key == "privacy" else "Termos de Uso"
    page = LegalPage.get_or_create(key, default_title)

    if request.method == "POST":
        page.title = (request.form.get("title") or page.title).strip() or page.title
        page.html = request.form.get("html", "")
        db.session.commit()
        flash("Página atualizada!", "success")
        return redirect(url_for("admin.admin_legal_edit", key=key))

    return render_template("legal_edit.html", page=page)


@admin.get('/faq')
@requires_auth
def admin_faq_list():
    items = FaqItem.query.order_by(FaqItem.position.asc(), FaqItem.id.asc()).all()
    return render_template('admin_faq.html', items=items)

@admin.post('/faq/new')
@requires_auth
def admin_faq_new():
    q = (request.form.get('question') or '').strip()
    a = (request.form.get('answer') or '').strip()
    pos = int(request.form.get('position') or 0)
    active = bool(request.form.get('active'))
    if not q:
        flash('Informe a pergunta.', 'danger')
        return redirect(url_for('admin.admin_faq_list'))
    item = FaqItem(question=q, answer=a, position=pos, active=active)
    db.session.add(item)
    db.session.commit()
    flash('Pergunta adicionada.', 'success')
    return redirect(url_for('admin.admin_faq_list'))

@admin.post('/faq/<int:fid>/update')
@requires_auth
def admin_faq_update(fid:int):
    item = FaqItem.query.get_or_404(fid)
    item.question = (request.form.get('question') or item.question).strip()
    item.answer = (request.form.get('answer') or item.answer).strip()
    item.position = int(request.form.get('position') or item.position)
    if 'active' in request.form:
        item.active = bool(request.form.get('active'))
    db.session.commit()
    flash('Pergunta atualizada.', 'success')
    return redirect(url_for('admin.admin_faq_list'))

@admin.post('/faq/<int:fid>/toggle')
@requires_auth
def admin_faq_toggle(fid:int):
    item = FaqItem.query.get_or_404(fid)
    item.active = not item.active
    db.session.commit()
    return redirect(url_for('admin.admin_faq_list'))

@admin.post('/faq/<int:fid>/delete')
@requires_auth
def admin_faq_delete(fid:int):
    item = FaqItem.query.get_or_404(fid)
    db.session.delete(item)
    db.session.commit()
    flash('Pergunta removida.', 'warning')
    return redirect(url_for('admin.admin_faq_list'))


@admin.get("/faq/init")
@requires_auth
def admin_faq_init():
    try:
        db.create_all()
        flash("Tabelas criadas/atualizadas.", "success")
    except Exception as e:
        flash(f"Erro ao criar tabelas: {e}", "danger")
    return redirect(url_for("admin.admin_faq_list"))

