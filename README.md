# MDY Rental Car – Landing (Flask + PostgreSQL + Docker)

Landing page HTML5 + Bootstrap com identidade MDY Rental Car e backend Flask/SQLAlchemy.
Recebe mensagens do formulário de contato e lista no /admin via Basic Auth.

## Rodando com Docker
1. `cp .env.example .env` (ajuste se quiser)
2. `docker compose up --build`
3. Site: http://localhost:8000
4. Admin (mensagens): http://localhost:8000/admin/messages  (login pelo `.env`)

## Sem Docker (opcional)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
export FLASK_APP=wsgi.py
flask run --port 8000
```

## Estrutura
- `app/templates/index.html` – landing multilíngue (PT/EN/ES)
- `app/templates/admin_messages.html` – listagem de mensagens
- `app/static/assets/` – logos e imagens (substitua hero.mp4 por um vídeo real quando desejar)
