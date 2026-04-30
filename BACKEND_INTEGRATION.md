# Django Backend Integration

The original [`index.html`](</c:/Users/yosee/Downloads/website-8bc5701e-e92d-4d07-bd0c-b88014c67587 (1)/index.html:1>) remains the source frontend file.

Backend integration is handled like this:

1. Django serves the existing `index.html` through `portfolio.views.frontend_shell`.
2. The response is sanitized to remove the hardcoded demo editor array from the delivered HTML.
3. Django injects a JSON bootstrap payload plus `static/portfolio/js/backend_bridge.js` at response time.
4. The bridge preserves the existing IDs, buttons, classes, and structure while replacing `localStorage` auth/data actions with Django session-backed requests.

Existing frontend inputs are mapped directly to Django forms:

- Sign up: `signupUsername`, `signupPassword`, `signupEmail`, `signupBio`
- Login: `loginUsername`, `loginPassword`
- Profile: `editBio`, `editAvatar`
- Contacts: `contactEmail`, `contactTelegram`, `contactWhatsapp`, `contactPhone`
- Videos: `videoTitle`, `videoUrl`, `videoThumb`, `videoType`, `videoCategory`, `videoDuration`, `editVideoId`

Backend endpoints used by the bridge:

- `POST /auth/signup/`
- `POST /auth/login/`
- `POST /auth/logout/`
- `GET /api/bootstrap/`
- `POST /api/profile/`
- `POST /api/contacts/`
- `POST /api/videos/create/`
- `POST /api/videos/<uuid>/update/`
- `POST /api/videos/<uuid>/delete/`
- `POST /api/videos/<uuid>/move/`
- `POST /api/profiles/<username>/videos/<uuid>/play/`

This keeps the frontend UI source untouched while moving persistence, authentication, CSRF protection, and business rules into Django.
