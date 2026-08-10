# Portfolio Show — Production Deployment Guide

This guide details step-by-step how to deploy **Portfolio Show** as two independent production applications on [Render](https://render.com) using [Neon PostgreSQL](https://neon.tech) for the database.

---

## Architecture Overview

```text
[Client Browser]
       │
       │  HTTP / HTTPS
       ▼
┌──────────────────────────────────────┐
│  FRONTEND (Render Static Site)       │
│  Root Directory: frontend            │
│  URL: https://portfolio-show.onrender.com
└──────────────────┬───────────────────┘
                   │
                   │ REST API (fetch with credentials: include)
                   ▼
┌──────────────────────────────────────┐
│  BACKEND (Render Web Service)        │
│  Root Directory: backend             │
│  URL: https://portfolio-show-api.onrender.com
└──────────┬──────────────┬────────────┘
           │              │
           ▼              ▼
┌──────────────────┐  ┌──────────────────┐
│ Neon PostgreSQL  │  │ Media Storage    │
│ (Database)       │  │ (Cloudinary)     │
└──────────────────┘  └──────────────────┘
```

---

## Step 1: Create Neon PostgreSQL Database

1. Sign up or log in at **[console.neon.tech](https://console.neon.tech)**.
2. Click **New Project** and name it `portfolio-show`.
3. Under **Dashboard → Connection Details**, select **Pooled connection**.
4. Copy the connection string:
   ```text
   postgresql://username:password@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   > 💡 **Note**: Make sure `?sslmode=require` is present at the end of the string. Neon requires SSL.

---

## Step 2: Deploy Backend (Render Web Service)

1. Log in to your **[Render Dashboard](https://dashboard.render.com)**.
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository containing Portfolio Show.
4. Configure the service settings:

| Setting | Value |
|---|---|
| **Name** | `portfolio-show-api` (or your choice) |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate` |
| **Start Command** | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |

5. Add Environment Variables:
   - `SECRET_KEY` = *(generate long random string)*
   - `DEBUG` = `False`
   - `DATABASE_URL` = `postgresql://user:pass@ep-xxx-pooler.neon.tech/neondb?sslmode=require`
   - `ALLOWED_HOSTS` = `portfolio-show-api.onrender.com`
   - `CSRF_TRUSTED_ORIGINS` = `https://portfolio-show-api.onrender.com`
   - `CORS_ORIGINS` = `https://portfolio-show.onrender.com` *(Fill after Step 3)*
   - `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET`
   - `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_WEBHOOK_SECRET`
   - `GEMINI_API_KEY` / `GROQ_API_KEY`

6. Click **Create Web Service**. Wait for the build and migration process to complete.

---

## Step 3: Deploy Frontend (Render Static Site)

1. In **Render Dashboard**, click **New +** → **Static Site**.
2. Connect the same GitHub repository.
3. Configure the static site settings:

| Setting | Value |
|---|---|
| **Name** | `portfolio-show` |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Build Command** | `sed -i "s|__ELA_API_URL_PLACEHOLDER__|${ELA_API_URL}|g" config.js` |
| **Publish Directory** | `.` |

4. Add Environment Variable:
   - `ELA_API_URL` = `https://portfolio-show-api.onrender.com` *(Backend URL)*

5. Click **Create Static Site**.
6. Once created, go to **Settings → Redirects / Rewrites** and add:

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | **Rewrite** |

---

## Step 4: Final Wire-up & Security Verification

1. **CORS Update**: Update backend `CORS_ORIGINS` variable with your Step 3 Frontend URL.
2. **Google OAuth Redirect URI**: In Google Cloud Console, set redirect URI to:
   `https://portfolio-show-api.onrender.com/accounts/google/login/callback/`
3. **Superuser**: In Render backend Shell tab, run `python manage.py createsuperuser` to create your admin login.
