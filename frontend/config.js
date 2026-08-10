/**
 * Portfolio Show — Frontend API Configuration
 *
 * This file sets window.__elaApiBase so that backend_bridge.js knows which
 * Django backend to talk to.
 *
 * HOW IT WORKS
 * ─────────────
 * 1. Local development:
 *    - Run the Django backend: cd backend && python manage.py runserver 8000
 *    - Serve the frontend: cd frontend && python -m http.server 5173
 *      (or use the dev-server helper: node dev-server.js)
 *    - This file sets API_URL to http://localhost:8000
 *
 * 2. Production (Render Static Site):
 *    - Set ELA_API_URL as an environment variable in the Render Static Site
 *      dashboard (e.g. https://portfolio-show-api.onrender.com)
 *    - The build command replaces __ELA_API_URL_PLACEHOLDER__ with the value
 *      from the env var before publishing.
 *    - Build command:
 *        sed -i "s|__ELA_API_URL_PLACEHOLDER__|${ELA_API_URL}|g" config.js
 *    - Or for Windows/PowerShell:
 *        (Get-Content config.js) -replace '__ELA_API_URL_PLACEHOLDER__', $env:ELA_API_URL | Set-Content config.js
 *
 * 3. Self-hosted / custom:
 *    - Edit API_URL below directly, or replace the placeholder via your own
 *      build/CI pipeline.
 *
 * IMPORTANT
 * ─────────
 * This file must be loaded BEFORE backend_bridge.js in index.html.
 * The <script src="...config.js"> tag must appear before
 * <script src="...backend_bridge.js">.
 */

(function () {
  // Placeholder replaced at deploy time. Falls back to localhost for dev.
  var API_URL = "__ELA_API_URL_PLACEHOLDER__";

  // If the placeholder was not replaced (local dev), use localhost
  if (!API_URL || API_URL === "__ELA_API_URL_PLACEHOLDER__" || API_URL.indexOf("__") === 0) {
    API_URL = "http://localhost:8000";
  }

  // Strip trailing slash for consistency
  window.__elaApiBase = API_URL.replace(/\/+$/, "");
})();
