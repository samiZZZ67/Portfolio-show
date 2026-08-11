# Portfolio Show

A role-based video portfolio platform. Video editors showcase their work, clients browse and request downloads, and administrators manage the system.

## Architecture

```
project/
├── frontend/          ← Static HTML/JS/CSS (deployed as Render Static Site)
└── backend/           ← Django REST API (deployed as Render Web Service)
```

The frontend and backend are **independently deployable**.

```
[Browser]
    │
    │  HTTP (fetch with credentials: include)
    ▼
[frontend/ — Render Static Site]
    │
    │  HTTPS API requests (ELA_API_URL)
    ▼
[backend/ — Render Web Service (Django)]
    │
    ├── Neon PostgreSQL
    ├── Cloudinary (media storage)
    └── Telegram Bot API
```

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
copy .env.example .env      # Edit with your values
python manage.py migrate
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
python -m http.server 5173
# Open http://localhost:5173
```

---

## Documentation

- [`backend/README.md`](backend/README.md) — Backend setup, API docs, Render deployment, Neon DB config
- [`frontend/README.md`](frontend/README.md) — Frontend setup, static site deployment, environment config

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS |
| Backend | Django 5.2, Django REST Framework |
| Database | Neon PostgreSQL (prod), SQLite (dev) |
| Auth | Django sessions + django-allauth + Google OAuth |
| Media | Cloudinary |
| Deployment | Render (Web Service + Static Site) |
| Notifications | Telegram Bot API |
| AI Assistants | Google Gemini, Groq |

---

## Features

- **Role-based access**: Admin, Editor, Client roles
- **Video portfolios**: Upload, manage, stream, and share video work
- **Secure downloads**: Client request → Owner approval → Signed download link
- **Telegram notifications**: Download request alerts via Telegram bot
- **AI assistant**: Groq + Gemini for editing briefs and bio generation
- **Google OAuth**: One-click sign-in with Google
- **Admin dashboard**: Manage roles, review requests, monitor activity

---

## Deployment

See individual README files for Render deployment instructions:
- Backend: `backend/README.md` → Render Web Service
- Frontend: `frontend/README.md` → Render Static Site
