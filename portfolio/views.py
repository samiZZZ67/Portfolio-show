import json
import re
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import F, Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.templatetags.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import ContactForm, LoginForm, ProfileForm, SignUpForm, VideoForm, VideoMoveForm
from .models import EditorProfile, PortfolioVideo

FRONTEND_SOURCE = Path(settings.BASE_DIR) / "index.html"
DEFAULT_EDITORS_PATTERN = re.compile(
    r"const DEFAULT_EDITORS = \[.*?\];\s*/\* State \*/",
    re.DOTALL,
)


def json_error_response(form, status=400):
    errors = form.errors.get_json_data()
    message = "Please correct the highlighted fields."
    for field_errors in errors.values():
        if field_errors:
            message = field_errors[0]["message"]
            break
    return JsonResponse(
        {
            "ok": False,
            "message": message,
            "errors": errors,
        },
        status=status,
    )


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Authentication required.",
                },
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def serialize_video(video):
    return {
        "id": str(video.id),
        "title": video.title,
        "url": video.url,
        "video_source": video.video_source,
        "uploaded_file_url": video.uploaded_file.url if video.uploaded_file else "",
        "uploaded_file_name": video.uploaded_file.name.rsplit("/", 1)[-1] if video.uploaded_file else "",
        "has_uploaded_file": video.has_uploaded_file,
        "playback_url": video.playback_url,
        "thumb": video.thumbnail_url,
        "type": video.content_type,
        "category": video.category,
        "duration": video.duration,
        "views": video.views,
    }


def serialize_editor(profile):
    return {
        "username": profile.user.username,
        "bio": profile.bio or EditorProfile.default_bio,
        "avatar": profile.avatar,
        "email": profile.user.email or "",
        "telegram": profile.telegram or "",
        "whatsapp": profile.whatsapp or "",
        "phone": profile.phone or "",
        "videos": [serialize_video(video) for video in profile.videos.all()],
    }


def editor_queryset():
    return EditorProfile.objects.select_related("user").prefetch_related(
        Prefetch(
            "videos",
            queryset=PortfolioVideo.objects.order_by("sort_order", "created_at"),
        )
    )


def visible_profiles(request):
    profiles = []
    for profile in editor_queryset():
        if profile.has_contact_method() or (
            request.user.is_authenticated and profile.user_id == request.user.id
        ):
            profiles.append(profile)
    return profiles


def build_bootstrap_payload(request):
    payload = {
        "current_user": request.user.username if request.user.is_authenticated else None,
        "editors": [],
    }
    for profile in visible_profiles(request):
        payload["editors"].append(serialize_editor(profile))
    return payload


def matches_search(profile, query, type_filter, category_filter):
    videos = list(profile.videos.all())
    normalized_query = query.strip().lower()

    if normalized_query:
        haystacks = [
            profile.user.username.lower(),
            (profile.bio or "").lower(),
        ]
        haystacks.extend(video.title.lower() for video in videos)
        haystacks.extend(video.category.lower() for video in videos)
        if not any(normalized_query in value for value in haystacks):
            return False

    if type_filter != "all" and not any(video.content_type == type_filter for video in videos):
        return False

    if category_filter != "all" and not any(video.category == category_filter for video in videos):
        return False

    return True


def sanitize_frontend_html(html):
    return DEFAULT_EDITORS_PATTERN.sub("const DEFAULT_EDITORS = [];\n\n/* State */", html, count=1)


def render_frontend_html(request):
    bootstrap_payload = build_bootstrap_payload(request)
    html = sanitize_frontend_html(FRONTEND_SOURCE.read_text(encoding="utf-8"))
    bootstrap_json = json.dumps(bootstrap_payload).replace("<", "\\u003c")
    injection = (
        "\n"
        f'<script id="ela-bootstrap" type="application/json">{bootstrap_json}</script>\n'
        f'<script src="{static("portfolio/js/backend_bridge.js")}"></script>\n'
    )
    if "</body>" not in html:
        raise Http404("Unable to attach backend bridge to the provided frontend.")
    return html.replace("</body>", f"{injection}</body>", 1)


def refresh_payload_response(request, message, extra=None, status=200):
    payload = build_bootstrap_payload(request)
    payload["ok"] = True
    payload["message"] = message
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def normalize_video_order(profile):
    ordered_videos = list(profile.videos.order_by("sort_order", "created_at"))
    dirty = []
    for index, video in enumerate(ordered_videos):
        if video.sort_order != index:
            video.sort_order = index
            dirty.append(video)
    if dirty:
        PortfolioVideo.objects.bulk_update(dirty, ["sort_order"])
    return ordered_videos


def get_owned_video(user, video_id):
    profile = user.editor_profile
    return get_object_or_404(profile.videos, pk=video_id)


@ensure_csrf_cookie
def frontend_shell(request, username=None):
    if username and not EditorProfile.objects.filter(user__username=username).exists():
        raise Http404("Editor not found.")
    return HttpResponse(render_frontend_html(request))


@require_GET
def bootstrap_view(request):
    return JsonResponse(build_bootstrap_payload(request))


@require_GET
def search_view(request):
    query = request.GET.get("q", "")
    type_filter = request.GET.get("type", "all")
    category_filter = request.GET.get("category", "all")
    editors = [
        serialize_editor(profile)
        for profile in visible_profiles(request)
        if matches_search(profile, query, type_filter, category_filter)
    ]
    return JsonResponse(
        {
            "editors": editors,
            "query": query,
            "type": type_filter,
            "category": category_filter,
        }
    )


@require_POST
def signup_view(request):
    if request.user.is_authenticated:
        return JsonResponse(
            {
                "ok": False,
                "message": "You are already signed in.",
            },
            status=400,
        )
    form = SignUpForm(request.POST)
    if not form.is_valid():
        return json_error_response(form)
    user = form.save()
    login(request, user)
    return refresh_payload_response(
        request,
        f"Welcome, {user.username}! Your portfolio is ready.",
        status=201,
    )


@require_POST
def login_view(request):
    form = LoginForm(request, request.POST)
    if not form.is_valid():
        return json_error_response(form)
    login(request, form.get_user())
    return refresh_payload_response(
        request,
        f"Welcome back, {request.user.username}!",
    )


@require_POST
def logout_view(request):
    logout(request)
    return refresh_payload_response(request, "Logged out successfully.")


@require_POST
@api_login_required
def profile_update_view(request):
    profile = request.user.editor_profile
    form = ProfileForm(request.POST, instance=profile)
    if not form.is_valid():
        return json_error_response(form)
    form.save()
    return refresh_payload_response(request, "Profile updated.")


@require_POST
@api_login_required
def contact_update_view(request):
    profile = request.user.editor_profile
    form = ContactForm(request.POST)
    if not form.is_valid():
        return json_error_response(form)
    form.save(request.user, profile)
    return refresh_payload_response(request, "Contact methods saved.")


@require_POST
@api_login_required
@transaction.atomic
def video_create_view(request):
    form = VideoForm(request.POST, request.FILES)
    if not form.is_valid():
        return json_error_response(form)
    profile = request.user.editor_profile
    video = form.save(commit=False)
    video.profile = profile
    video.sort_order = profile.videos.count()
    video.save()
    return refresh_payload_response(
        request,
        "Video added successfully.",
        extra={"video_id": str(video.id)},
        status=201,
    )


@require_POST
@api_login_required
def video_update_view(request, video_id):
    video = get_owned_video(request.user, video_id)
    form = VideoForm(request.POST, request.FILES, instance=video)
    if not form.is_valid():
        return json_error_response(form)
    form.save()
    return refresh_payload_response(request, "Video updated successfully.")


@require_POST
@api_login_required
@transaction.atomic
def video_delete_view(request, video_id):
    video = get_owned_video(request.user, video_id)
    profile = request.user.editor_profile
    video.delete()
    normalize_video_order(profile)
    return refresh_payload_response(request, "Video deleted.")


@require_POST
@api_login_required
@transaction.atomic
def video_move_view(request, video_id):
    form = VideoMoveForm(request.POST)
    if not form.is_valid():
        return json_error_response(form)
    profile = request.user.editor_profile
    ordered_videos = normalize_video_order(profile)
    current_index = next(
        (index for index, video in enumerate(ordered_videos) if video.id == video_id),
        None,
    )
    if current_index is None:
        raise Http404("Video not found.")

    direction = form.cleaned_data["direction"]
    swap_index = current_index - 1 if direction == "up" else current_index + 1
    if swap_index < 0 or swap_index >= len(ordered_videos):
        return JsonResponse(
            {
                "ok": False,
                "message": "Video cannot be moved further in that direction.",
            },
            status=400,
        )

    current_video = ordered_videos[current_index]
    swap_video = ordered_videos[swap_index]
    current_video.sort_order, swap_video.sort_order = swap_video.sort_order, current_video.sort_order
    PortfolioVideo.objects.bulk_update([current_video, swap_video], ["sort_order"])
    return refresh_payload_response(request, "Video order updated.")


@require_POST
@transaction.atomic
def video_play_view(request, username, video_id):
    profile = get_object_or_404(
        editor_queryset(),
        user__username=username,
    )
    if not profile.has_contact_method() and (
        not request.user.is_authenticated or request.user.id != profile.user_id
    ):
        raise Http404("Editor not found.")

    video = get_object_or_404(profile.videos, pk=video_id)
    PortfolioVideo.objects.filter(pk=video.pk).update(views=F("views") + 1)
    video.refresh_from_db(fields=["views"])
    return refresh_payload_response(
        request,
        "View recorded.",
        extra={
            "video": serialize_video(video),
            "profile_username": username,
        },
    )
