from __future__ import annotations
from datetime import datetime
from .extensions import db

# ----- Mensagens de contato (já existia) -----
class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ContactMessage {self.id} {self.email}>"

# ----- Configurações simples do site -----
class SiteSetting(db.Model):
    __tablename__ = "site_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)

    @staticmethod
    def get_value(key: str, default: str | None = None) -> str | None:
        s = SiteSetting.query.filter_by(key=key).first()
        return s.value if s and s.value is not None else default

    @staticmethod
    def set_value(key: str, value: str | None) -> "SiteSetting":
        s = SiteSetting.query.filter_by(key=key).first()
        if not s:
            s = SiteSetting(key=key, value=value)
            db.session.add(s)
        else:
            s.value = value
        db.session.commit()
        return s

    @staticmethod
    def get_settings() -> dict[str, str | None]:
        # Retorna todas as chaves/valores de configuração em um dicionário
        return {s.key: s.value for s in SiteSetting.query.all()}

# ----- Frota Destaque -----
class FeaturedCategory(db.Model):
    __tablename__ = "featured_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    image_url = db.Column(db.String(255))
    active = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    image = db.Column(db.LargeBinary)

    items = db.relationship(
        "FeaturedItem",
        backref="category",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="FeaturedItem.position.asc()",
    )

    def __repr__(self) -> str:
        return f"<FeaturedCategory {self.slug} active={self.active}>"

class FeaturedItem(db.Model):
    __tablename__ = "featured_items"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("featured_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(180), nullable=False)       # Ex.: "BMW 320i Sport"
    subtitle = db.Column(db.String(220))                    # Ex.: "2023 • Automático"
    image_path = db.Column(db.String(320))                  # Ex.: "assets/sedan.jpg"
    active = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<FeaturedItem {self.title} active={self.active}>"

# --- CRM: pedidos de cotação ---
class QuoteRequest(db.Model):
    __tablename__ = "quote_requests"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # dados do formulário
    pickup_place = db.Column(db.String(160), nullable=False)
    pickup_date = db.Column(db.String(20), nullable=False)   # ISO (yyyy-mm-dd) vindo do input date
    drop_place   = db.Column(db.String(160), nullable=False)
    drop_date    = db.Column(db.String(20), nullable=False)

    name     = db.Column(db.String(120), nullable=False)
    phone    = db.Column(db.String(50),  nullable=False)
    category = db.Column(db.String(80),  nullable=False)

    # metadados úteis
    source     = db.Column(db.String(80),  nullable=True)   # ex.: 'hero'
    user_agent = db.Column(db.Text,        nullable=True)
    ip_addr    = db.Column(db.String(64),  nullable=True)
    status     = db.Column(db.String(24),  nullable=False, default="novo")  # novo | em_contato | concluido

    def __repr__(self) -> str:
        return f"<QuoteRequest id={self.id} {self.name} {self.pickup_date}->{self.drop_date}>"


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Location {self.id} {self.name!r} active={self.active}>"

# --- Páginas legais editáveis no admin ----------------------------
class LegalPage(db.Model):
    __tablename__ = "legal_pages"
    id = db.Column(db.Integer, primary_key=True)
    # key: "privacy" ou "terms"
    key = db.Column(db.String(32), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    html = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_or_create(key: str, title: str):
        obj = LegalPage.query.filter_by(key=key).first()
        if not obj:
            obj = LegalPage(key=key, title=title, html="")
            db.session.add(obj)
            db.session.commit()
        return obj


class FaqItem(db.Model):
    __tablename__ = "faq_items"

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(400), nullable=False)
    answer = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self) -> str:
        return f"<FaqItem {self.id} {self.question!r}>"
    
    