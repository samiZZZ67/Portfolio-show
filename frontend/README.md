# Portfolio Show — Frontend

Static HTML/CSS/JS frontend for the Portfolio Show platform.

## Structure

```
frontend/
├── index.html                  # Main single-page application shell
├── config.js                   # API URL configuration (loaded before bridge)
├── static/
│   └── portfolio/
│       └── js/
│           └── backend_bridge.js   # Connects frontend to Django backend API
├── public/
│   ├── favicon.ico
│   ├── favicon.png
│   └── apple-touch-icon.png
├── .env.example                # Environment variable template
└── README.md
```

---

## How It Works

The frontend is a **self-contained static HTML/JS/CSS application** (no build step required).

1. **`config.js`** runs first and sets `window.__elaApiBase` to the backend URL
2. **`backend_bridge.js`** reads `window.__elaApiBase`, then on page load:
   - Calls `GET /api/bootstrap/` to load user state, editor list, and config
   - Intercepts all UI interactions and routes them to the Django REST API
   - Manages session-based authentication via cross-origin cookies

---

## Local Development

### Prerequisites
- The Django backend running at `http://localhost:8000`
- Any static file server (Python, Node, nginx)

### Setup

```bash
cd frontend

# Option 1: Python simple HTTP server
python -m http.server 5173

# Option 2: Node http-server
npx http-server -p 5173

# Option 3: VS Code Live Server extension
# Just open index.html → Right click → Open with Live Server
```

Open `http://localhost:5173` in your browser.

> **Note:** Make sure the Django backend is running at `http://localhost:8000` (or set `ELA_API_URL` accordingly).

### API URL for development

The default `config.js` points to `http://localhost:8000`. No changes needed for standard local dev.

To use a different backend URL, either:
1. Edit `config.js` directly (revert before committing), or
2. Set the `ELA_API_URL` environment variable and run the build command

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ELA_API_URL` | Django backend base URL | `http://localhost:8000` |

---

## Deployment on Render (Static Site)

### New Static Site

1. Connect your GitHub repo
2. Set **Root Directory** to `frontend`
3. Set **Build Command**:

   **Linux/macOS (Render):**
   ```bash
   sed -i "s|__ELA_API_URL_PLACEHOLDER__|${ELA_API_URL}|g" config.js
   ```

4. Set **Publish Directory** to `.` (or `frontend` if using root)
5. Add environment variable:
   - `ELA_API_URL` = `https://your-backend.onrender.com`

### How the build command works

`config.js` contains the placeholder `__ELA_API_URL_PLACEHOLDER__`. The `sed` command replaces it with the actual backend URL at deploy time, so `window.__elaApiBase` is set correctly in production.

### Render rewrite rules

Add this rewrite rule in the Render Static Site settings so all paths serve `index.html` (for client-side routing):

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | Rewrite |

---

## Adding Static Files

Static assets (CSS, JS, images) go in `static/portfolio/`. Reference them in `index.html` as:

```html
<link rel="stylesheet" href="/static/portfolio/css/style.css">
<script src="/static/portfolio/js/my-script.js"></script>
```

Favicons go in `public/` and are referenced as `/favicon.ico`.

---

## Google OAuth Note

Google OAuth redirects go through the **backend** (Django handles the OAuth callback). After login, the backend session is established and the frontend picks it up via the next `GET /api/bootstrap/` call.

Make sure the Google OAuth redirect URI in your Google Console points to:
```
https://your-backend.onrender.com/accounts/google/login/callback/
```

**Not** the frontend URL.
