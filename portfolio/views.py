import html
import json
import re
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import Count, F, Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import ContactForm, LoginForm, ProfileForm, SignUpForm, VideoForm, VideoMoveForm
from .models import AccountRole, EditorProfile, FollowRelationship, PortfolioVideo

FRONTEND_SOURCE = Path(settings.BASE_DIR) / "index.html"
DEFAULT_EDITORS_PATTERN = re.compile(
    r"const DEFAULT_EDITORS = \[.*?\];\s*/\* State \*/",
    re.DOTALL,
)
TITLE_PATTERN = re.compile(r"<title>.*?</title>", re.DOTALL | re.IGNORECASE)


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


def api_editor_required(view_func):
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
        if not request.user.editor_profile.is_editor:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Only editor accounts can manage portfolios.",
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def profile_queryset():
    return (
        EditorProfile.objects.select_related("user")
        .annotate(
            followers_total=Count("follower_relationships", distinct=True),
            following_total=Count("following_relationships", distinct=True),
        )
        .prefetch_related(
            Prefetch(
                "videos",
                queryset=PortfolioVideo.objects.order_by("sort_order", "created_at"),
            )
        )
    )


def viewer_profile(request):
    if request.user.is_authenticated:
        return request.user.editor_profile
    return None


def visible_profile(profile, request):
    if request.user.is_authenticated and profile.user_id == request.user.id:
        return True
    return profile.has_contact_method()


def visible_profiles(request):
    return [profile for profile in profile_queryset() if visible_profile(profile, request)]


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


def serialize_profile(profile, following_ids=None, current_profile=None):
    videos = list(profile.videos.all())
    setup_state = {
        "needs_avatar": not profile.has_custom_avatar,
        "needs_contact": not profile.has_contact_method(),
        "needs_video": profile.is_editor and not videos,
    }
    setup_state["is_complete"] = not any(setup_state.values())

    return {
        "username": profile.user.username,
        "display_name": profile.display_name,
        "cname": profile.cname or "",
        "role": profile.role,
        "role_label": profile.get_role_display(),
        "bio": profile.bio or EditorProfile.default_bio,
        "avatar": profile.avatar,
        "avatar_url": profile.avatar_url or "",
        "has_custom_avatar": profile.has_custom_avatar,
        "email": profile.user.email or "",
        "telegram": profile.telegram or "",
        "whatsapp": profile.whatsapp or "",
        "phone": profile.phone or "",
        "other_contacts": profile.other_contacts or [],
        "videos": [serialize_video(video) for video in videos],
        "followers_count": getattr(profile, "followers_total", profile.follower_relationships.count()),
        "following_count": getattr(profile, "following_total", profile.following_relationships.count()),
        "is_following": bool(following_ids and profile.id in following_ids),
        "can_edit": bool(current_profile and current_profile.id == profile.id),
        "public_url": f"/{profile.user.username}/",
        "setup": setup_state,
    }


def build_bootstrap_payload(request):
    current_profile = viewer_profile(request)
    following_ids = set()
    if current_profile:
        following_ids = set(
            current_profile.following_relationships.values_list("followed_id", flat=True)
        )

    payload = {
        "current_user": request.user.username if request.user.is_authenticated else None,
        "current_user_role": current_profile.role if current_profile else None,
        "editors": [],
    }
    for profile in visible_profiles(request):
        payload["editors"].append(
            serialize_profile(
                profile,
                following_ids=following_ids,
                current_profile=current_profile,
            )
        )
    return payload


def matches_search(profile, query, type_filter, category_filter):
    videos = list(profile.videos.all())
    normalized_query = query.strip().lower()

    if normalized_query:
        haystacks = [
            profile.user.username.lower(),
            profile.display_name.lower(),
            (profile.bio or "").lower(),
            profile.get_role_display().lower(),
        ]
        haystacks.extend(video.title.lower() for video in videos)
        haystacks.extend(video.category.lower() for video in videos)
        haystacks.extend(str(item.get("label", "")).lower() for item in (profile.other_contacts or []))
        if not any(normalized_query in value for value in haystacks):
            return False

    if type_filter != "all" and not any(video.content_type == type_filter for video in videos):
        return False

    if category_filter != "all" and not any(video.category == category_filter for video in videos):
        return False

    return True


def sanitize_frontend_html(html_source):
    return DEFAULT_EDITORS_PATTERN.sub("const DEFAULT_EDITORS = [];\n\n/* State */", html_source, count=1)


def build_seo_injection(request, requested_profile=None):
    if requested_profile:
        title = f"{requested_profile.display_name} (@{requested_profile.user.username}) | Ela-sam Portfolio Show"
        description = (
            requested_profile.bio
            or f"View {requested_profile.display_name}'s portfolio on Ela-sam Portfolio Show."
        )
        canonical = request.build_absolute_uri(f"/{requested_profile.user.username}/")
        structured_data = {
            "@context": "https://schema.org",
            "@type": "Person" if requested_profile.is_editor else "ProfilePage",
            "name": requested_profile.display_name,
            "alternateName": requested_profile.user.username,
            "description": description,
            "url": canonical,
            "image": request.build_absolute_uri(requested_profile.avatar),
        }
    elif request.path == "/discover/":
        title = "Discover Editors | Ela-sam Portfolio Show"
        description = "Search and discover editors, portfolios, and contact methods on Ela-sam Portfolio Show."
        canonical = request.build_absolute_uri("/discover/")
        structured_data = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Discover Editors",
            "description": description,
            "url": canonical,
        }
    else:
        title = "Ela-sam Portfolio Show"
        description = "The professional platform where video editors and creative clients connect."
        canonical = request.build_absolute_uri("/")
        structured_data = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Ela-sam Portfolio Show",
            "url": canonical,
            "potentialAction": {
                "@type": "SearchAction",
                "target": request.build_absolute_uri("/discover/") + "?q={search_term_string}",
                "query-input": "required name=search_term_string",
            },
        }

    escaped_title = html.escape(title)
    escaped_description = html.escape(description[:160])
    escaped_canonical = html.escape(canonical)
    structured_json = json.dumps(structured_data).replace("<", "\\u003c")

    return (
        f"<title>{escaped_title}</title>\n"
        f'<meta name="description" content="{escaped_description}">\n'
        '<meta name="robots" content="index,follow">\n'
        f'<link rel="canonical" href="{escaped_canonical}">\n'
        f'<meta property="og:title" content="{escaped_title}">\n'
        f'<meta property="og:description" content="{escaped_description}">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:url" content="{escaped_canonical}">\n'
        f'<meta name="twitter:title" content="{escaped_title}">\n'
        f'<meta name="twitter:description" content="{escaped_description}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<script type="application/ld+json">{structured_json}</script>\n'
    )


def render_frontend_html(request, requested_profile=None):
    bootstrap_payload = build_bootstrap_payload(request)
    html_source = sanitize_frontend_html(FRONTEND_SOURCE.read_text(encoding="utf-8"))
    seo_injection = build_seo_injection(request, requested_profile=requested_profile)
    bootstrap_json = json.dumps(bootstrap_payload).replace("<", "\\u003c")

    if TITLE_PATTERN.search(html_source):
        html_source = TITLE_PATTERN.sub(seo_injection.strip(), html_source, count=1)
    elif "</head>" in html_source:
        html_source = html_source.replace("</head>", f"{seo_injection}</head>", 1)

    injection = (
        "\n"
        f'<script id="ela-bootstrap" type="application/json">{bootstrap_json}</script>\n'
        f'<script src="{static("portfolio/js/backend_bridge.js")}"></script>\n'
    )
    if "</body>" not in html_source:
        raise Http404("Unable to attach backend bridge to the provided frontend.")
    return html_source.replace("</body>", f"{injection}</body>", 1)


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


def friendly_not_found_response(request, requested_path="", status=404):
    return render(
        request,
        "404.html",
        {
            "requested_path": requested_path or request.path,
            "home_url": reverse("portfolio:home"),
            "discover_url": reverse("portfolio:discover"),
        },
        status=status,
    )


@ensure_csrf_cookie
def frontend_shell(request, username=None):
    requested_profile = None
    if username:
        requested_profile = profile_queryset().filter(user__username=username).first()
        if not requested_profile or not visible_profile(requested_profile, request):
            return friendly_not_found_response(request, requested_path=f"/{username}/", status=404)
    return HttpResponse(render_frontend_html(request, requested_profile=requested_profile))


@require_GET
def bootstrap_view(request):
    return JsonResponse(build_bootstrap_payload(request))


@require_GET
def search_view(request):
    query = request.GET.get("q", "")
    type_filter = request.GET.get("type", "all")
    category_filter = request.GET.get("category", "all")
    current_profile = viewer_profile(request)
    following_ids = (
        set(current_profile.following_relationships.values_list("followed_id", flat=True))
        if current_profile
        else set()
    )
    editors = [
        serialize_profile(
            profile,
            following_ids=following_ids,
            current_profile=current_profile,
        )
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
    form = SignUpForm(request.POST, request.FILES)
    if not form.is_valid():
        return json_error_response(form)
    user = form.save()
    login(request, user)
    welcome_message = (
        f"Welcome, {user.editor_profile.display_name}! Your portfolio is ready."
        if user.editor_profile.role == AccountRole.EDITOR
        else f"Welcome, {user.editor_profile.display_name}! Your client account is ready."
    )
    return refresh_payload_response(
        request,
        welcome_message,
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
        f"Welcome back, {request.user.editor_profile.display_name}!",
    )


@require_POST
def logout_view(request):
    logout(request)
    return refresh_payload_response(request, "Logged out successfully.")


@require_POST
@api_login_required
def profile_update_view(request):
    profile = request.user.editor_profile
    form = ProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
    if not form.is_valid():
        return json_error_response(form)
    form.save()
    return refresh_payload_response(
        request,
        "Profile updated.",
        extra={"updated_username": request.user.username},
    )


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
def follow_toggle_view(request, username):
    follower = request.user.editor_profile
    followed = get_object_or_404(EditorProfile, user__username=username)

    if follower.pk == followed.pk:
        return JsonResponse(
            {
                "ok": False,
                "message": "You cannot follow your own account.",
            },
            status=400,
        )

    relationship = FollowRelationship.objects.filter(follower=follower, followed=followed)
    if relationship.exists():
        relationship.delete()
        message = f"You unfollowed {followed.display_name}."
    else:
        FollowRelationship.objects.create(follower=follower, followed=followed)
        message = f"You followed {followed.display_name}."

    return refresh_payload_response(request, message)


@require_POST
@api_editor_required
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
@api_editor_required
def video_update_view(request, video_id):
    video = get_owned_video(request.user, video_id)
    form = VideoForm(request.POST, request.FILES, instance=video)
    if not form.is_valid():
        return json_error_response(form)
    form.save()
    return refresh_payload_response(request, "Video updated successfully.")


@require_POST
@api_editor_required
@transaction.atomic
def video_delete_view(request, video_id):
    video = get_owned_video(request.user, video_id)
    profile = request.user.editor_profile
    video.delete()
    normalize_video_order(profile)
    return refresh_payload_response(request, "Video deleted.")


@require_POST
@api_editor_required
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
    profile = profile_queryset().filter(user__username=username).first()
    if not profile or not visible_profile(profile, request):
        raise Http404("Profile not found.")

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


@require_GET
def robots_txt_view(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri(reverse('portfolio:sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def friendly_not_found_view(request, requested_path=""):
    return friendly_not_found_response(request, requested_path=requested_path, status=404)
