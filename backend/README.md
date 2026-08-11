# Portfolio Show — Backend

Django 5.2 REST API backend for the Portfolio Show platform.

## Tech Stack

- **Framework**: Django 5.2 + Django REST Framework
- **Database**: Neon PostgreSQL (production) / SQLite (local dev)
- **Auth**: Django sessions + django-allauth (Google OAuth)
- **Media Storage**: Cloudinary
- **Deployment**: Render Web Service

---

## Local Development

### Prerequisites
- Python 3.12+
- pip

### Setup

```bash
cd backend

# 1. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux
# Edit .env with your values

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Collect static files (optional for dev)
python manage.py collectstatic --noinput

# 7. Run development server
python manage.py runserver 8000
```

The backend will be available at `http://localhost:8000`.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

### Required for production

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key (generate a long random string) |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

### Neon PostgreSQL

Get your connection string from the [Neon Console](https://console.neon.tech):

```
postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require
```

Neon provides both a **direct** and **pooled** connection string. Use the pooled one (`-pooler` in the hostname) for production.

SSL is enforced automatically when the hostname contains `.neon.tech`.

---

## API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup/` | Register new user |
| `POST` | `/auth/login/` | Log in |
| `POST` | `/auth/logout/` | Log out |
| `GET` | `/auth/google/` | Start Google OAuth |

### Core API
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/bootstrap/` | Get full app state (user, editors, config) |
| `GET` | `/api/search/` | Search editors/videos |
| `POST` | `/api/profile/` | Update profile |
| `POST` | `/api/contacts/` | Update contact info |
| `POST` | `/api/follow/<username>/toggle/` | Follow/unfollow |

### Video Management
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/videos/create/` | Upload new video |
| `POST` | `/api/videos/<uuid>/update/` | Update video |
| `POST` | `/api/videos/<uuid>/delete/` | Delete video |
| `POST` | `/api/videos/<uuid>/move/` | Reorder video |
| `POST` | `/api/profiles/<user>/videos/<uuid>/play/` | Increment view count |
| `POST` | `/api/profiles/<user>/videos/<uuid>/like/` | Toggle like |
| `POST` | `/api/profiles/<user>/videos/<uuid>/rate/` | Submit rating |

### Secure Video (authenticated)
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/secure/videos/upload/` | Upload video file to Cloudinary |
| `GET` | `/api/secure/videos/<uuid>/stream/` | Get signed stream token |
| `GET` | `/api/secure/videos/<uuid>/download/` | Get signed download link |
| `POST` | `/api/secure/videos/<uuid>/download-request/` | Request download access |

### Admin
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/secure/admin/overview/` | Admin dashboard data |
| `POST` | `/api/secure/admin/profiles/<user>/role/` | Change user role |
| `GET` | `/api/secure/download-requests/` | List download requests |
| `POST` | `/api/secure/download-requests/<id>/review/` | Approve/reject request |

### AI Assistants
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ai/groq/` | Chat with Groq AI |
| `POST` | `/api/ai/gemini/` | Chat with Gemini AI |

### Other
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/telegram/webhook/<secret>/` | Telegram bot webhook |
| `GET` | `/api/profiles/<user>/avatar/` | Serve profile avatar |

---

## Deployment on Render

### New Web Service

1. Connect your GitHub repo
2. Set **Root Directory** to `backend`
3. Set **Runtime** to `Python 3`
4. Set **Build Command**:
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
   ```
5. Set **Start Command**:
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```
6. Add all environment variables from `.env.example`

### Environment variables to set in Render

- `SECRET_KEY` — generate with: `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DATABASE_URL` — from Neon console (pooled connection string, with `?sslmode=require`)
- `CORS_ORIGINS` — your Render Static Site URL (e.g. `https://portfolio-show.onrender.com`)
- `CSRF_TRUSTED_ORIGINS` — your backend Render URL
- `ALLOWED_HOSTS` — your backend Render hostname
- `CLOUDINARY_*` — from Cloudinary console
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — from Google Console
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_WEBHOOK_SECRET` — from Telegram BotFather
- `GEMINI_API_KEY` / `GROQ_API_KEY` — from respective API consoles

---

## Neon Database Setup

1. Create an account at [neon.tech](https://neon.tech)
2. Create a new project
3. Copy the **pooled connection string** (includes `-pooler` in hostname)
4. Add `?sslmode=require` if not already present
5. Set as `DATABASE_URL` environment variable
6. Run `python manage.py migrate` to create tables

---

## Running Tests

```bash
cd backend
python manage.py test portfolio
```

---

## CORS Configuration

The backend uses `django-cors-headers` to allow the frontend to make credentialed cross-origin requests.

Set `CORS_ORIGINS` to a comma-separated list of allowed frontend origins:

```env
CORS_ORIGINS=https://portfolio-show.onrender.com,http://localhost:5173
```

In development, `http://localhost:5173` and `http://localhost:3000` are allowed by default.

**Never use `CORS_ALLOW_ALL_ORIGINS=True` with session authentication.**

---

## Session Cookies (Cross-Origin)

When the frontend and backend are on different domains, session cookies require:
- `SESSION_COOKIE_SAMESITE=None`
- `SESSION_COOKIE_SECURE=True`

This is applied automatically in production (`IS_RENDER=True`). For local dev with cross-origin, set:

```env
FORCE_CROSS_ORIGIN_COOKIES=true
```
