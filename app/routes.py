import re
import unicodedata
from flask import (
    Blueprint, render_template, request, jsonify,
    current_app, send_from_directory, url_for
)
from app.extensions import db
from app.models import (
    Location, QuoteRequest, ContactMessage, SiteSetting,
    LegalPage, FeaturedCategory
)
from .models import FaqItem

from supabase import create_client, Client
import os

site_bp = Blueprint("site", __name__)


# ---------- utils ----------
def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def _slug_key(s: str) -> str:
    """
    Normaliza slugs para chave de comparação.
    """
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")

    # dobras úteis
    if s == "sedans":
        s = "sedan"
    if s == "suv":
        s = "suvs"  # usamos 'suvs' como chave canônica
    if s in ("especial", "special"):
        s = "especial"
    return s


def _resolve_image_url(v: str) -> str:
    if not v:
        return ""
    v = v.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    filename = v.split("/")[-1]
    try:
        return url_for("site.uploads", filename=filename, _external=False)
    except Exception:
        return f"/uploads/{filename}"


@site_bp.get("/health/supabase")
def health_supabase():
    import os
    from app.extensions import supabase
    return jsonify({
        "supabase_client": bool(supabase is not None),
        "envs": {
            "SUPABASE_URL": bool(os.getenv("SUPABASE_URL")),
            "SUPABASE_SERVICE_ROLE_KEY": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
            "SUPABASE_BUCKET": bool(os.getenv("SUPABASE_BUCKET")),
        }
    }), 200


url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)


# ---------- health & uploads ----------
@site_bp.get("/health")
def health():
    return "ok", 200


@site_bp.get("/uploads/<path:filename>")
def uploads(filename):
    """
    Serve os arquivos diretamente do Supabase, se disponível.
    """
    try:
        # Crie o cliente do Supabase
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        supabase = create_client(url, key)
        
        # Verifique se o cliente foi criado corretamente
        if not supabase:
            return jsonify({"error": "Falha ao inicializar cliente do Supabase"}), 500

        # Obtenha a URL pública do arquivo no Supabase
        file_url = supabase.storage.from_("mdy-uploads").get_public_url(filename)

        # Verifique se o arquivo existe
        if not file_url:
            return jsonify({"error": "Arquivo não encontrado"}), 404

        return jsonify({"file_url": file_url["publicURL"]})
    except Exception as e:
        # Caso ocorra um erro, retorne uma mensagem
        print(f"Erro ao acessar o arquivo: {e}")
        return jsonify({"error": f"Erro ao buscar o arquivo: {str(e)}"}), 500




# ---------- páginas ----------
@site_bp.get("/")
def home():
    # WhatsApp do admin
    whatsapp_raw = SiteSetting.get_value("whatsapp_number", "") or ""
    whatsapp = digits_only(whatsapp_raw)

    # categorias indexadas por slug normalizado
    all_cats = {}
    for c in FeaturedCategory.query.all():
        k = _slug_key(c.slug or "")
        if k:
            all_cats[k] = c

    # slots fixos exibidos na home
    desired = [
        ("Compacto", "compacto"),
        ("Sedan", "sedan"),
        ("SUVs", "suvs"),
        ("Minivans", "minivans"),
        ("Luxo", "luxo"),
        ("Especial", "especial"),
    ]

    grid_slots = []
    for name, want_slug in desired:
        c = all_cats.get(_slug_key(want_slug))
        if not c:
            # variantes comuns digitadas no admin
            variantes = {
                "sedan": ["sedans", "sedã", "sedan"],
                "suvs": ["suv"],
                "especial": ["special"],
            }.get(want_slug, [])
            for v in variantes:
                c = all_cats.get(_slug_key(v))
                if c:
                    break

        if c:
            grid_slots.append(
                {
                    "name": c.name or name,
                    "slug": _slug_key(c.slug),
                    "active": bool(c.active),
                    # >>> AQUI: sempre converte para URL servível
                    "image": _resolve_image_url(c.image_url),
                }
            )
        else:
            grid_slots.append(
                {
                    "name": f"{name} (configurar no admin)",
                    "slug": want_slug,
                    "active": False,
                    "image": "",
                }
            )

    return render_template("index.html", whatsapp=whatsapp, grid_slots=grid_slots)


# ---------- API ----------
@site_bp.get("/api/locations")
def api_locations():
    rows = (
        Location.query.filter_by(active=True)
        .order_by(Location.position.asc())
        .all()
    )
    return jsonify([{"id": r.id, "name": r.name} for r in rows])


@site_bp.post("/api/quote")
def api_quote():
    data = request.get_json(silent=True) or {}
    required = [
        "pickup_place",
        "pickup_date",
        "drop_place",
        "drop_date",
        "name",
        "phone",
        "category",
    ]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return (
            jsonify(
                ok=False,
                error=f"Campos obrigatórios ausentes: {', '.join(missing)}",
            ),
            400,
        )

    q = QuoteRequest(
        pickup_place=data["pickup_place"].strip(),
        pickup_date=data["pickup_date"].strip(),
        drop_place=data["drop_place"].strip(),
        drop_date=data["drop_date"].strip(),
        name=data["name"].strip(),
        phone=data["phone"].strip(),
        category=data["category"].strip(),
        source=(data.get("source") or "home").strip(),
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_addr=request.headers.get("X-Forwarded-For", request.remote_addr or "")[
            :45
        ],
        status="novo",
    )
    db.session.add(q)
    db.session.commit()
    return jsonify(ok=True, id=q.id)


@site_bp.post("/api/contact")
def api_contact():
    data = request.get_json(silent=True) or {}
    required = ["name", "email", "message"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return (
            jsonify(
                ok=False,
                error=f"Campos obrigatórios ausentes: {', '.join(missing)}",
            ),
            400,
        )
    m = ContactMessage(
        name=data["name"].strip(),
        email=data["email"].strip(),
        message=data["message"].strip(),
        ip_addr=request.headers.get("X-Forwarded-For", request.remote_addr or "")[
            :45
        ],
        user_agent=request.headers.get("User-Agent", "")[:255],
    )
    db.session.add(m)
    db.session.commit()
    return jsonify(ok=True, id=m.id)


# ---------- páginas legais ----------
@site_bp.get("/privacy")
def privacy_page():
    page = LegalPage.get_or_create("privacy", "Política de Privacidade")
    return render_template("legal_public.html", page=page)


@site_bp.get("/terms")
def terms_page():
    page = LegalPage.get_or_create("terms", "Termos de Uso")
    return render_template("legal_public.html", page=page)


# ---------- FAQ ----------
@site_bp.get("/faq")
def faq_page():
    whatsapp_raw = SiteSetting.get_value("whatsapp_number", "") or ""
    whatsapp = digits_only(whatsapp_raw)

    items = (
        FaqItem.query.filter_by(active=True)
        .order_by(FaqItem.position.asc(), FaqItem.id.asc())
        .all()
    )
    return render_template("faq.html", items=items, whatsapp=whatsapp)
