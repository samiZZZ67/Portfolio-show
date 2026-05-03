import json
import logging
import mimetypes
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.http import FileResponse
from django.urls import reverse
from django.utils import timezone

from portfolio.models import (
    AccountRole,
    DownloadRequestStatus,
    VideoDownloadGrant,
    OwnerNotification,
    OwnerNotificationType,
    PortfolioVideo,
    VideoAccessEventType,
    VideoAccessLog,
    VideoLike,
    VideoPlatform,
    VideoRating,
    VideoSourceType,
)

logger = logging.getLogger(__name__)

STREAM_TOKEN_SALT = "secure-video-stream"
DOWNLOAD_TOKEN_SALT = "secure-video-download"


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_user_agent(request):
    return (request.META.get("HTTP_USER_AGENT", "") or "")[:255]


def build_viewer_hash(request):
    user_id = request.user.pk if request.user.is_authenticated else "anon"
    raw_value = f"{user_id}|{get_client_ip(request)}|{get_user_agent(request)}"
    return signing.Signer(salt="secure-video-viewer").sign(raw_value).split(":", 1)[1]


def is_publicly_viewable(video, request):
    if request.user.is_authenticated and video.profile.user_id == request.user.id:
        return True
    return video.profile.is_public_profile


def resolve_field_storage(field_file):
    storage = getattr(field_file, "storage", None)
    resolver = getattr(storage, "_get_storage", None)
    if callable(resolver):
        try:
            return resolver()
        except Exception:
            return storage
    return storage


def uses_local_filesystem_storage(field_file):
    return isinstance(resolve_field_storage(field_file), FileSystemStorage)


def open_local_media_file(field_file):
    if uses_local_filesystem_storage(field_file):
        return field_file.open("rb")

    name = (getattr(field_file, "name", "") or "").lstrip("/\\")
    if not name:
        return None
    candidate = (Path(settings.MEDIA_ROOT) / name).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        candidate.relative_to(media_root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate.open("rb")
    return None


def cloudinary_public_id_for_video(video):
    if video.storage_public_id:
        return video.storage_public_id
    if video.uploaded_file and not uses_local_filesystem_storage(video.uploaded_file):
        return video.uploaded_file.name
    return ""


def build_watermark_text(request, viewer_hash):
    if request.user.is_authenticated:
        label = request.user.email or request.user.username
    else:
        label = f"Guest-{viewer_hash[:8]}"
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
    return f"{label} | {timestamp}"


def build_text_watermark_transformation(viewer_text):
    encoded_text = quote(viewer_text, safe="")
    return (
        f"l_text:Arial_28_bold:{encoded_text},co_white,o_55"
        "/fl_layer_apply,g_south_east,x_24,y_24"
    )


def build_cloudinary_auth_token(expires_at):
    if not (settings.CLOUDINARY_AUTH_TOKEN_KEY and settings.SECURE_VIDEO_USE_CLOUDINARY_TOKENS):
        return None
    return {
        "key": settings.CLOUDINARY_AUTH_TOKEN_KEY,
        "expiration": int(expires_at.timestamp()),
    }


def build_cloudinary_delivery_url(video, *, expires_at, watermark_text="", as_attachment=False):
    public_id = cloudinary_public_id_for_video(video)
    if not public_id:
        raise ValueError("Video is missing a Cloudinary public ID.")

    options = {
        "resource_type": "video",
        "type": "upload",
        "secure": True,
        "sign_url": True,
    }
    auth_token = build_cloudinary_auth_token(expires_at)
    if auth_token:
        options["auth_token"] = auth_token
    if watermark_text and video.watermark_enabled:
        options["transformation"] = build_text_watermark_transformation(watermark_text)
    if as_attachment:
        options["flags"] = "attachment"

    url, _extra = cloudinary_url(public_id, **options)
    return url


def proxy_cloudinary_asset(url, *, fallback_name, inline):
    upstream = urlopen(Request(url, headers={"User-Agent": "ElaSamSecureProxy/1.0"}))
    content_type = upstream.headers.get_content_type() or mimetypes.guess_type(fallback_name)[0] or "application/octet-stream"
    response = FileResponse(upstream, content_type=content_type)
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{fallback_name}"'
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    if content_length := upstream.headers.get("Content-Length"):
        response["Content-Length"] = content_length
    return response


def issue_stream_token(request, video):
    viewer_hash = build_viewer_hash(request)
    expires_at = timezone.now() + timedelta(seconds=settings.SECURE_VIDEO_STREAM_TTL_SECONDS)
    watermark_text = build_watermark_text(request, viewer_hash)
    token = signing.dumps(
        {
            "video_id": str(video.id),
            "viewer_hash": viewer_hash,
            "mode": "stream",
            "watermark_text": watermark_text,
        },
        salt=STREAM_TOKEN_SALT,
    )
    return token, expires_at, watermark_text, viewer_hash


def issue_download_token(user, video, download_request):
    expires_at = timezone.now() + timedelta(seconds=settings.SECURE_VIDEO_DOWNLOAD_TTL_SECONDS)
    token = signing.dumps(
        {
            "video_id": str(video.id),
            "user_id": user.id,
            "download_request_id": download_request.id if download_request else None,
            "mode": "download",
        },
        salt=DOWNLOAD_TOKEN_SALT,
    )
    return token, expires_at


def verify_stream_token(token, request):
    payload = signing.loads(
        token,
        salt=STREAM_TOKEN_SALT,
        max_age=settings.SECURE_VIDEO_STREAM_TTL_SECONDS,
    )
    if payload.get("viewer_hash") != build_viewer_hash(request):
        raise signing.BadSignature("Viewer fingerprint mismatch.")
    return payload


def verify_download_token(token, request):
    payload = signing.loads(
        token,
        salt=DOWNLOAD_TOKEN_SALT,
        max_age=settings.SECURE_VIDEO_DOWNLOAD_TTL_SECONDS,
    )
    if not request.user.is_authenticated or payload.get("user_id") != request.user.id:
        raise signing.BadSignature("Download token does not belong to this user.")
    return payload


def current_like_state(video, viewer_hash):
    like = VideoLike.objects.filter(video=video, viewer_hash=viewer_hash).first()
    return bool(like and like.is_active)


def like_count(video):
    return video.public_likes.filter(is_active=True).count()


def rating_summary(video):
    aggregate = video.public_ratings.aggregate(avg=Avg("score"), count=Count("id"))
    average = round(float(aggregate["avg"] or 0), 1)
    return average, int(aggregate["count"] or 0)


def active_download_grant_for(video, user):
    if not user or not user.is_authenticated or user.id == video.profile.user_id:
        return None
    return VideoDownloadGrant.objects.filter(
        user=user,
        video=video,
        is_active=True,
        revoked_at__isnull=True,
    ).first()


def user_can_download_video(user, video):
    if not user or not user.is_authenticated:
        return False
    if user.id == video.profile.user_id:
        return True
    return active_download_grant_for(video, user) is not None


def grant_download_access(download_request, reviewer):
    grant, _created = VideoDownloadGrant.objects.update_or_create(
        source_request=download_request,
        defaults={
            "user": download_request.requester,
            "video": download_request.video,
            "granted_by": reviewer,
            "is_active": True,
            "revoked_at": None,
        },
    )
    return grant


def revoke_download_access(download_request):
    grant = VideoDownloadGrant.objects.filter(
        user=download_request.requester,
        video=download_request.video,
        is_active=True,
    ).first()
    if grant:
        grant.is_active = False
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["is_active", "revoked_at"])
    return grant


def record_access_event(event_type, *, video, request, user=None, download_request=None, viewer_hash="", metadata=None):
    VideoAccessLog.objects.create(
        video=video,
        actor_user=user,
        download_request=download_request,
        event_type=event_type,
        viewer_hash=viewer_hash,
        ip_address=get_client_ip(request) or None,
        user_agent=get_user_agent(request),
        metadata=metadata or {},
    )


def store_secure_video_asset(video, uploaded_file):
    video.video_source = VideoSourceType.UPLOAD
    video.url = ""
    video.original_filename = uploaded_file.name
    video.original_format = Path(uploaded_file.name).suffix.lstrip(".").lower()
    video.original_file_size = uploaded_file.size

    if settings.CLOUDINARY_MEDIA_ENABLED:
        upload_response = cloudinary.uploader.upload_large(
            uploaded_file,
            resource_type="video",
            public_id=f"secure_videos/{video.profile.user.username}/{video.id.hex}",
            overwrite=False,
            unique_filename=False,
            access_control=[{"access_type": "token"}],
            context={
                "owner_username": video.profile.user.username,
                "platform": video.platform or VideoPlatform.OTHER,
            },
        )
        public_id = upload_response["public_id"]
        video.uploaded_file.name = public_id
        video.storage_public_id = public_id
        video.original_width = upload_response.get("width") or video.original_width
        video.original_height = upload_response.get("height") or video.original_height
        video.original_format = upload_response.get("format") or video.original_format
        video.original_file_size = upload_response.get("bytes") or video.original_file_size
        video.original_bitrate = upload_response.get("bit_rate") or upload_response.get("bitrate")
        frame_rate = upload_response.get("frame_rate")
        if frame_rate is not None:
            video.frame_rate = str(frame_rate)
        return upload_response

    video.uploaded_file = uploaded_file
    video.storage_public_id = ""
    return None


def create_owner_notification(*, owner, notification_type, video, title, message, download_request=None, payload=None):
    return OwnerNotification.objects.create(
        owner=owner,
        notification_type=notification_type,
        video=video,
        download_request=download_request,
        title=title,
        message=message,
        payload=payload or {},
    )


def send_telegram_message(chat_id, text):
    if not chat_id:
        raise ValueError("Telegram chat ID is required.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Telegram bot token is not configured.")

    telegram_url = f"{settings.TELEGRAM_API_BASE}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
        }
    ).encode("utf-8")
    request_obj = Request(
        telegram_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    response = urlopen(request_obj, timeout=10)
    response_payload = json.loads(response.read().decode("utf-8") or "{}")
    if not response_payload.get("ok"):
        raise RuntimeError("Telegram API did not confirm delivery.")
    message_id = str(response_payload.get("result", {}).get("message_id", "") or "")
    if not message_id:
        raise RuntimeError("Telegram delivery response did not include a message ID.")
    return message_id


def notify_admins_about_download_request_issue(download_request, *, reason):
    owner = download_request.video.profile.user
    video_title = download_request.video_title_snapshot or download_request.video.title
    preview_url = download_request.video_preview_url_snapshot or download_request.video.thumbnail_url
    title = "Download request needs admin follow-up"
    reason_line = (
        "The video owner is missing a Telegram chat ID."
        if reason == "missing_owner_chat_id"
        else "Telegram delivery to the video owner failed."
    )
    message_lines = [
        reason_line,
        f"Request ID: {download_request.id}",
        f"Owner: {owner.username}",
        f"Requester: {download_request.requester.username}",
        f"Video: {video_title}",
        f"Time: {download_request.requested_at.isoformat()}",
    ]
    if preview_url:
        message_lines.append(f"Preview: {preview_url}")
    message = "\n".join(message_lines)
    payload = {
        "reason": reason,
        "request_id": download_request.id,
        "owner_username": owner.username,
        "requester": download_request.requester.username,
        "video_title": video_title,
        "video_preview_url": preview_url,
        "status": download_request.status,
    }

    admin_users = (
        User.objects.filter(
            Q(is_staff=True) | Q(is_superuser=True) | Q(editor_profile__role=AccountRole.ADMIN)
        )
        .exclude(pk=owner.pk)
        .distinct()
    )
    for admin_user in admin_users:
        create_owner_notification(
            owner=admin_user,
            notification_type=OwnerNotificationType.DOWNLOAD_REQUEST,
            video=download_request.video,
            title=title,
            message=message,
            download_request=download_request,
            payload=payload,
        )
        if admin_user.email:
            try:
                send_mail(
                    subject=title,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("Failed to send admin fallback download request email.")


def notify_owner_about_download_request(download_request, request):
    owner = download_request.video.profile.user
    title = "New download request"
    video_title = download_request.video_title_snapshot or download_request.video.title
    preview_url = download_request.video_preview_url_snapshot or download_request.video.thumbnail_url
    message_lines = [
        "This request is for YOUR uploaded video.",
        f"Download request #{download_request.id}",
        f"Requester: {download_request.requester.username}",
        f"Video: {video_title}",
        f"Time: {download_request.requested_at.isoformat()}",
    ]
    if preview_url:
        message_lines.append(f"Preview: {preview_url}")
    message = "\n".join(message_lines)
    create_owner_notification(
        owner=owner,
        notification_type=OwnerNotificationType.DOWNLOAD_REQUEST,
        video=download_request.video,
        title=title,
        message=message,
        download_request=download_request,
        payload={
            "request_id": download_request.id,
            "requester": download_request.requester.username,
            "video_title": video_title,
            "video_preview_url": preview_url,
            "status": download_request.status,
        },
    )

    if owner.email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[owner.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send owner download request email.")

    if download_request.video.profile.telegram_chat_id:
        try:
            message_id = send_telegram_message(download_request.video.profile.telegram_chat_id, message)
            download_request.telegram_chat_id = download_request.video.profile.telegram_chat_id
            download_request.telegram_message_id = message_id
            download_request.save(update_fields=["telegram_chat_id", "telegram_message_id"])
            return {
                "delivery_confirmed": True,
                "delivery_status": "telegram_delivered",
                "delivery_message": "Request successfully delivered to the video owner's Telegram.",
                "telegram_message_id": message_id,
            }
        except Exception:
            logger.exception("Failed to send owner download request Telegram message.")
            notify_admins_about_download_request_issue(
                download_request,
                reason="owner_telegram_delivery_failed",
            )
            return {
                "delivery_confirmed": False,
                "delivery_status": "admin_fallback_delivery_failed",
                "delivery_message": (
                    "Request saved, but Telegram delivery to the video owner could not be confirmed. "
                    "Admin follow-up was notified."
                ),
                "telegram_message_id": "",
            }
    else:
        notify_admins_about_download_request_issue(
            download_request,
            reason="missing_owner_chat_id",
        )
        return {
            "delivery_confirmed": False,
            "delivery_status": "admin_fallback_missing_owner_chat_id",
            "delivery_message": (
                "Request saved, but the video owner does not have a Telegram chat ID yet. "
                "Admin follow-up was notified."
            ),
            "telegram_message_id": "",
        }


def notify_requester_about_download_decision(download_request):
    video_title = download_request.video_title_snapshot or download_request.video.title
    approved = download_request.status == DownloadRequestStatus.APPROVED
    title = "Download request approved" if approved else "Download request rejected"
    decision_line = (
        f"Your request for '{video_title}' was approved."
        if approved
        else f"Your request for '{video_title}' was rejected."
    )
    message_lines = [
        decision_line,
        f"Request ID: {download_request.id}",
        f"Video: {video_title}",
        (
            "Download access is now enabled for this specific video."
            if approved
            else "Access was not granted for this specific video."
        ),
    ]
    if download_request.owner_response_message:
        message_lines.append(f"Owner response: {download_request.owner_response_message}")
    message = "\n".join(message_lines)

    requester_email = (download_request.requester.email or "").strip()
    if requester_email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester_email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Failed to send requester download decision email.")

    requester_chat_id = getattr(download_request.requester.editor_profile, "telegram_chat_id", "").strip()
    if requester_chat_id:
        try:
            send_telegram_message(requester_chat_id, message)
        except Exception:
            logger.exception("Failed to send requester download decision Telegram message.")


def build_stream_file_url(request, video, token):
    endpoint = reverse("portfolio:secure-video-stream-file", kwargs={"video_id": video.id})
    return request.build_absolute_uri(f"{endpoint}?token={quote(token)}")


def build_download_file_url(request, video, token):
    endpoint = reverse("portfolio:secure-video-download-file", kwargs={"video_id": video.id})
    return request.build_absolute_uri(f"{endpoint}?token={quote(token)}")
