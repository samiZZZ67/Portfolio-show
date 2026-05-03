# Role-Based Video Platform Guide

This guide is written for the current Django project in this repository.

## 1. Current Repo Fit

Your project already has a strong starting point:

- `portfolio/models.py`
  - `PortfolioVideo`
  - `VideoDownloadRequest`
  - `OwnerNotification`
  - `VideoAccessLog`
  - public `VideoLike` and `VideoRating`
- `portfolio/api_secure/views.py`
  - secure upload
  - signed stream session
  - signed download link
  - owner request review API
- `portfolio/api_secure/services.py`
  - Cloudinary token-based delivery
  - signed access tokens
  - Telegram send support
  - access logging

The main gaps versus your requested system are:

- no business-level `ADMIN` role in the current role model
- the current `EditorProfile` role only covers `editor` and `client`
- dashboards are not fully separated by role
- download approval currently relies only on approved request state
- no dedicated per-video grant model
- Telegram currently sends a plain message, not actionable approve/reject controls
- editor skills are not modeled yet

## 2. Recommended Target Design

Use three layers of permission:

1. Authentication
   - Django session auth for web users
   - every protected endpoint requires authenticated user

2. Role authorization
   - `ADMIN`, `EDITOR`, `CLIENT`
   - enforced in Python on every dashboard and API endpoint

3. Resource authorization
   - even after role passes, check ownership or explicit per-video grant
   - never trust frontend buttons

Recommended route split:

- `/django-admin/`
  - built-in Django admin for superuser maintenance only
- `/admin/`
  - custom business admin dashboard
- `/editor/`
  - editor dashboard
- `/client/`
  - client dashboard
- `/api/`
  - role-aware APIs
- `/api/telegram/webhook/<secret>/`
  - Telegram callback/webhook endpoint

## 3. Model Design

Because this repo already uses `django.contrib.auth.models.User`, the lowest-risk production path is:

- keep Django `User`
- keep a one-to-one profile model
- expand the profile to carry role metadata
- add dedicated models for skills and download grants

If you have not launched yet and are comfortable with an auth migration, a custom `User` model is cleaner long term. For this repo, the profile-based approach is safer.

### Role enum

```python
class AccountRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    EDITOR = "editor", "Editor"
    CLIENT = "client", "Client"
```

### Account profile

You can keep the existing `EditorProfile` class name for migration safety, but it should behave like a general account profile.

```python
class EditorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="editor_profile")
    role = models.CharField(max_length=10, choices=AccountRole.choices, db_index=True)
    cname = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    avatar_file = models.FileField(upload_to=profile_avatar_upload_to, blank=True, max_length=500)
    avatar_url = models.URLField(max_length=500, blank=True)
    telegram = models.CharField(max_length=64, blank=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True)
    whatsapp = models.CharField(max_length=32, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    other_contacts = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Editor skill tags

Use normalized tags instead of a JSON list. That keeps filtering, admin search, and reporting easy.

```python
class SkillTag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)

class EditorSkill(models.Model):
    profile = models.ForeignKey(EditorProfile, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(SkillTag, on_delete=models.CASCADE, related_name="editors")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["profile", "skill"], name="unique_editor_skill")
        ]
```

Examples:

- CapCut
- Adobe Premiere Pro
- After Effects
- Photoshop
- DaVinci Resolve

### Video

Your current `PortfolioVideo` model is already close. The main business rule is that `profile.user` is the owner.

Recommended additions:

- `is_active = models.BooleanField(default=True)`
- `visibility = models.CharField(...)` if you plan private/internal videos later
- keep `storage_public_id`, `original_filename`, `thumbnail_url`
- keep `watermark_enabled`

### Access request

Store request snapshots so Telegram and audit records remain stable even if the video title changes later.

```python
class VideoDownloadRequest(models.Model):
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_download_requests")
    video = models.ForeignKey(PortfolioVideo, on_delete=models.CASCADE, related_name="download_requests")
    status = models.CharField(max_length=12, choices=DownloadRequestStatus.choices, default=DownloadRequestStatus.PENDING, db_index=True)
    video_title_snapshot = models.CharField(max_length=255)
    video_preview_url_snapshot = models.URLField(max_length=500, blank=True)
    request_message = models.TextField(blank=True)
    owner_response_message = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_video_download_requests")
    telegram_message_id = models.CharField(max_length=64, blank=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["requester", "video"], name="unique_video_download_request_per_user")
        ]
```

### Per-video download grant

Do not rely only on `status=approved`. Use an explicit grant model.

```python
class VideoDownloadGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="video_download_grants")
    video = models.ForeignKey(PortfolioVideo, on_delete=models.CASCADE, related_name="download_grants")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="granted_video_downloads")
    source_request = models.OneToOneField(VideoDownloadRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="download_grant")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "video"], condition=models.Q(is_active=True), name="unique_active_download_grant")
        ]
```

Why this matters:

- one request approves one exact video only
- you can revoke later without deleting audit history
- download permission becomes a simple server-side existence check

### Notifications and audit

Keep your existing models and slightly expand them:

- `OwnerNotification`
  - keep for in-app owner/admin inbox
- `VideoAccessLog`
  - keep for audit trail
  - log stream token issuance, stream file access, request creation, request decision, download link issuance, and final download

## 4. Role Matrix

### ADMIN

- can access `/admin/`
- can view all users, all videos, all requests
- can approve or reject any pending request
- should not share editor or client dashboard routes
- may use Django superuser for platform maintenance

### EDITOR

- can access `/editor/`
- can upload videos
- can edit only their own profile and videos
- can review requests for videos they own
- can directly download only their own uploaded videos

### CLIENT

- can access `/client/`
- can watch public/allowed videos
- can like and rate videos
- can request download access
- cannot upload videos
- cannot directly download unless a grant exists

## 5. Authentication and Routing Logic

Create one central role resolver and use it everywhere.

```python
def get_user_role(user):
    if not user.is_authenticated:
        return None
    if hasattr(user, "editor_profile"):
        return user.editor_profile.role
    return None

def role_home_url(user):
    role = get_user_role(user)
    if role == AccountRole.ADMIN:
        return reverse("portfolio:admin-dashboard")
    if role == AccountRole.EDITOR:
        return reverse("portfolio:editor-dashboard")
    if role == AccountRole.CLIENT:
        return reverse("portfolio:client-dashboard")
    return reverse("portfolio:home")
```

On login:

- authenticate user
- resolve role
- redirect:
  - `admin -> /admin/`
  - `editor -> /editor/`
  - `client -> /client/`

Do not use frontend-only redirection. The Django login view or login handler must send the correct redirect URL.

### Strict dashboard guard

```python
def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            role = get_user_role(request.user)
            if role not in allowed_roles:
                raise PermissionDenied("You are not allowed to access this dashboard.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
```

Use:

- `@role_required(AccountRole.ADMIN)` for admin views
- `@role_required(AccountRole.EDITOR)` for editor views
- `@role_required(AccountRole.CLIENT)` for client views

For DRF, create parallel permission classes:

- `IsAdminRole`
- `IsEditorRole`
- `IsClientRole`
- `IsVideoOwnerOrGranted`

## 6. Download Restriction Logic

Use one service function as the single source of truth.

```python
def can_download_video(user, video):
    if not user.is_authenticated:
        return False
    if user.id == video.profile.user_id:
        return True
    return VideoDownloadGrant.objects.filter(
        user=user,
        video=video,
        is_active=True,
        revoked_at__isnull=True,
    ).exists()
```

Enforce this in two places:

1. download-link endpoint
2. final file-download endpoint

That second check prevents direct URL bypass.

Recommended flow:

- client opens video detail
- frontend asks API for video permissions
- if `can_download_video == true`, show Download
- else show Request Access
- when Request Access is clicked, call secure request endpoint

Never render raw Cloudinary download URLs directly to the client. Your current signed-token + proxy pattern in `portfolio/api_secure/services.py` is the right production pattern.

## 7. Access Request Workflow

### Step 1. Create request

On `POST /api/videos/<video_id>/download-request/`:

- verify authenticated user
- reject if requester is owner
- reject if an active grant already exists
- create or update request with:
  - `requester`
  - `video`
  - `video_title_snapshot = video.title`
  - `video_preview_url_snapshot = video.thumbnail_url or secure preview URL`
  - `status = pending`
  - `request_message`

### Step 2. Notify owner on Telegram

Send Telegram message to `video.profile.telegram_chat_id`.

Message body should include:

- requester username
- video title
- preview URL or video link
- request timestamp
- request ID

Use Telegram inline keyboard buttons:

- `Approve`
- `Reject`

Recommended payload:

```json
{
  "chat_id": "OWNER_CHAT_ID",
  "text": "Download request #42\nRequester: client_a\nVideo: Product Launch Edit\nPreview: https://...\nTime: 2026-05-03T12:30:00Z",
  "reply_markup": {
    "inline_keyboard": [
      [
        {"text": "Approve", "callback_data": "dr:42:approve:<signed>"},
        {"text": "Reject", "callback_data": "dr:42:reject:<signed>"}
      ]
    ]
  }
}
```

Do not trust raw callback data. Sign it with Django signing or include a short-lived signed token.

### Step 3. Review decision

Allow review from two actors:

- owner editor
- admin

First valid decision wins unless you explicitly build an admin override flow.

Decision rules:

- reviewer must be request owner or admin
- request must still be pending
- action must be approve or reject

### Approve path

On approval:

- set request `status = approved`
- set `reviewed_at`
- set `approved_at`
- set `reviewed_by`
- create `VideoDownloadGrant(user=requester, video=video, granted_by=reviewer, source_request=request)`
- notify requester in-app
- optionally send Telegram or email to requester

User notification should include:

- video title
- secure video page link
- message that download access was granted

### Reject path

On rejection:

- set request `status = rejected`
- set `reviewed_at`
- set `reviewed_by`
- do not create grant
- notify requester in-app

User notification should include:

- video title
- message: `Your request for this video was rejected`

## 8. Telegram Integration Design

Use Telegram webhook mode, not polling, on Render.

Recommended endpoints:

- `POST /api/telegram/webhook/<secret>/`

Webhook responsibilities:

- verify webhook secret path
- parse `callback_query`
- extract signed request action token
- validate signature and actor ownership
- approve or reject the request
- answer callback query
- edit the Telegram message so the editor sees the final status

Recommended helper functions:

- `send_download_request_telegram_message(download_request)`
- `build_telegram_request_message(download_request)`
- `build_telegram_inline_keyboard(download_request)`
- `handle_telegram_callback(update_payload)`
- `approve_download_request(download_request, reviewer, source="telegram")`
- `reject_download_request(download_request, reviewer, source="telegram")`

The current repo already has `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_BASE`, and a Telegram send block in `portfolio/api_secure/services.py`. Extend that block instead of starting over.

## 9. Security Rules

### Role separation

- never decide access from frontend role flags alone
- every dashboard view checks backend role
- every API endpoint checks backend role

### Download bypass protection

- signed short-lived download URLs only
- verify token and permission again at file endpoint
- do not expose raw Cloudinary public URLs

### Cloudinary

- keep secure video uploads token-protected
- keep proxy or signed-auth delivery
- keep `watermark_enabled` for stream sessions

### Render deployment

Set:

- `DEBUG=False`
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")`
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`

Also add:

- `SECURE_HSTS_SECONDS`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `SECURE_HSTS_PRELOAD`
- `REFERRER_POLICY = "same-origin"`

### Abuse controls

- keep DRF throttles
- add throttles for Telegram webhook if needed
- log request creation and decision events
- make review actions idempotent

## 10. Recommended File Changes In This Repo

### `portfolio/models.py`

- add `ADMIN` to `AccountRole`
- extend `EditorProfile`
- add `SkillTag`
- add `EditorSkill`
- add `video_title_snapshot` and `video_preview_url_snapshot` to `VideoDownloadRequest`
- add `telegram_message_id` and `telegram_chat_id` to `VideoDownloadRequest`
- add `VideoDownloadGrant`

### `portfolio/forms.py`

- allow admin role only through secure admin creation flow, not public signup
- expose editor skill editing in profile form
- keep client signup separate from editor signup if UX should be strict

### `portfolio/views.py`

- add role-based login redirect
- add admin/editor/client dashboard views
- block wrong-role dashboard access with 403 or redirect to correct dashboard

### `portfolio/api_secure/permissions.py`

- add `IsAdminRole`
- add `IsEditorRole`
- add `IsClientRole`
- add object-level permission helper for download grants

### `portfolio/api_secure/views.py`

- update request create API to save video snapshots
- allow owner or admin request review
- change download access check from approved request lookup to grant lookup
- add permission-state field to video serializers if desired

### `portfolio/api_secure/services.py`

- add `can_download_video`
- add `create_download_grant`
- add `approve_download_request`
- add `reject_download_request`
- replace simple Telegram text send with inline keyboard callback flow

### `portfolio/api_secure/serializers.py`

- include:
  - `video_preview_url_snapshot`
  - `video_title_snapshot`
  - grant state
  - reviewer metadata

### `portfolio/urls.py`

- add:
  - `/admin/`
  - `/editor/`
  - `/client/`
  - Telegram webhook route

### `config/settings.py`

- add:
  - `TELEGRAM_WEBHOOK_SECRET`
  - `APP_BASE_URL`
  - stronger production security settings

## 11. Suggested Implementation Sequence

1. Extend role model to include `ADMIN`.
2. Add skill models and profile editing support.
3. Add `VideoDownloadGrant`.
4. Add request snapshot fields.
5. Refactor download permission checks to use grant model.
6. Add strict dashboard routes and role redirect logic.
7. Upgrade Telegram messaging to inline action callbacks.
8. Add requester notification flow after approve/reject.
9. Add admin dashboard screens for global oversight.
10. Add tests for each role boundary and download path.

## 12. Minimum Test Matrix

- admin cannot access editor dashboard as editor content owner
- editor cannot access admin dashboard
- client cannot access admin or editor dashboard
- editor can upload video
- client cannot upload video
- owner can download own uploaded video
- non-owner without grant cannot download
- non-owner with approved grant can download only that video
- download token cannot be reused after expiry
- Telegram callback cannot approve a request for the wrong owner
- admin can review any pending request
- second review attempt on already reviewed request fails safely

## 13. Best-Practice Notes

- Keep business admin UI separate from Django admin.
- Do not allow public signup into `ADMIN`.
- Prefer explicit grant models over inferring access from request status.
- Store snapshot values inside request records for audit integrity.
- Keep all security-critical logic in service functions so both web views and Telegram webhook reuse the same rules.
- Continue using short-lived signed URLs and final endpoint re-validation.

## 14. Final Recommendation

For this specific repo, do not rewrite everything.

Build on the secure foundation you already have:

- keep `PortfolioVideo`
- keep `VideoDownloadRequest`
- keep the secure stream/download token flow
- add strict role enforcement
- add explicit per-video grants
- add Telegram callback actions
- separate dashboards by role

That gives you a production-ready design without throwing away the secure video work already present in `portfolio/api_secure`.
