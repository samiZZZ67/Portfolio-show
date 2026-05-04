from datetime import timedelta
from urllib.parse import unquote

from cloudinary.exceptions import Error as CloudinaryError
from django.db import DatabaseError, transaction
from django.db.models import Count, F
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from portfolio.models import (
    AccountRole,
    DownloadRequestStatus,
    EditorProfile,
    OwnerNotification,
    PortfolioVideo,
    VideoAccessEventType,
    VideoDownloadRequest,
    VideoLike,
    VideoRating,
    VideoSourceType,
)

from .permissions import (
    IsAuthenticatedAdmin,
    IsAuthenticatedEditor,
    IsAuthenticatedEditorOrAdmin,
    IsAuthenticatedUser,
    has_admin_role,
)
from .serializers import (
    DownloadLinkSerializer,
    DownloadRequestCreateSerializer,
    DownloadRequestReviewSerializer,
    OwnerNotificationSerializer,
    PublicVideoLikeStateSerializer,
    PublicVideoRatingSerializer,
    PublicVideoRatingStateSerializer,
    SecureVideoSerializer,
    SecureVideoUploadSerializer,
    StreamSessionSerializer,
    VideoDownloadRequestSerializer,
)
from .services import (
    build_cloudinary_delivery_url,
    build_download_file_url,
    build_stream_file_url,
    build_viewer_hash,
    cloudinary_public_id_for_video,
    current_like_state,
    active_download_grant_for,
    grant_download_access,
    get_client_ip,
    issue_download_token,
    issue_stream_token,
    is_publicly_viewable,
    like_count,
    notify_requester_about_download_decision,
    notify_owner_about_download_request,
    open_local_media_file,
    proxy_cloudinary_asset,
    rating_summary,
    record_access_event,
    revoke_download_access,
    store_secure_video_asset,
    user_can_download_video,
    verify_download_token,
    verify_stream_token,
)
from .throttles import (
    SecureOwnerNotificationsThrottle,
    SecureOwnerReviewThrottle,
    SecureVideoDownloadLinkThrottle,
    SecureVideoDownloadRequestThrottle,
    SecureVideoLikeThrottle,
    SecureVideoRatingThrottle,
    SecureVideoStreamThrottle,
    SecureVideoUploadThrottle,
)


def secure_video_queryset():
    return PortfolioVideo.objects.select_related("profile", "profile__user")


def get_secure_video_or_404(video_id):
    return get_object_or_404(secure_video_queryset(), pk=video_id)


def assert_video_is_public_or_owned(video, request):
    if not is_publicly_viewable(video, request):
        raise Http404("Video not found.")


def serialize_admin_profile(profile):
    videos_count = getattr(profile, "videos_count", 0)
    setup_state = {
        "needs_avatar": not profile.has_custom_avatar,
        "needs_contact": not profile.has_contact_method(),
        "needs_video": profile.is_editor and not videos_count,
    }
    setup_state["is_complete"] = not any(setup_state.values())
    contact_methods_count = sum(
        1
        for value in (profile.user.email, profile.telegram, profile.telegram_chat_id, profile.whatsapp, profile.phone)
        if value
    ) + len(profile.other_contacts or [])
    return {
        "user_id": profile.user_id,
        "username": profile.user.username,
        "display_name": profile.display_name,
        "role": profile.role,
        "role_label": profile.get_role_display(),
        "email": profile.user.email or "",
        "telegram": profile.telegram or "",
        "telegram_chat_id": profile.telegram_chat_id or "",
        "whatsapp": profile.whatsapp or "",
        "phone": profile.phone or "",
        "contact_methods_count": contact_methods_count,
        "public_url": f"/{profile.user.username}/",
        "is_public_profile": profile.is_public_profile,
        "has_custom_avatar": profile.has_custom_avatar,
        "videos_count": videos_count,
        "followers_count": getattr(profile, "followers_count", 0),
        "following_count": getattr(profile, "following_count", 0),
        "clients_served": profile.clients_served,
        "completed_projects": profile.completed_projects,
        "updated_at": profile.updated_at,
        "setup": setup_state,
    }


class AdminOverviewAPIView(APIView):
    permission_classes = (IsAuthenticatedAdmin,)
    throttle_classes = (SecureOwnerNotificationsThrottle,)

    def get(self, request):
        profiles = list(
            EditorProfile.objects.select_related("user")
            .annotate(
                videos_count=Count("videos", distinct=True),
                followers_count=Count("follower_relationships", distinct=True),
                following_count=Count("following_relationships", distinct=True),
            )
            .order_by("role", "user__username")
        )
        videos = PortfolioVideo.objects.all()
        download_requests = VideoDownloadRequest.objects.all()
        unread_notifications_total = OwnerNotification.objects.filter(is_read=False).count()
        serialized_profiles = [serialize_admin_profile(profile) for profile in profiles]
        profiles_needing_setup_total = sum(
            1 for profile in serialized_profiles if not profile["setup"]["is_complete"]
        )
        public_profiles_total = sum(1 for profile in serialized_profiles if profile["is_public_profile"])

        summary = {
            "users_total": len(serialized_profiles),
            "admins_total": sum(1 for profile in serialized_profiles if profile["role"] == AccountRole.ADMIN),
            "editors_total": sum(1 for profile in serialized_profiles if profile["role"] == AccountRole.EDITOR),
            "clients_total": sum(1 for profile in serialized_profiles if profile["role"] == AccountRole.CLIENT),
            "public_profiles_total": public_profiles_total,
            "private_profiles_total": max(0, len(serialized_profiles) - public_profiles_total),
            "profiles_needing_setup_total": profiles_needing_setup_total,
            "videos_total": videos.count(),
            "uploaded_videos_total": videos.exclude(uploaded_file="").count(),
            "pending_download_requests_total": download_requests.filter(
                status=DownloadRequestStatus.PENDING
            ).count(),
            "approved_download_requests_total": download_requests.filter(
                status=DownloadRequestStatus.APPROVED
            ).count(),
            "rejected_download_requests_total": download_requests.filter(
                status=DownloadRequestStatus.REJECTED
            ).count(),
            "unread_notifications_total": unread_notifications_total,
        }
        recent_videos = [
            {
                "id": str(video.id),
                "title": video.title,
                "owner_username": video.profile.user.username,
                "category": video.category,
                "content_type": video.content_type,
                "has_uploaded_file": video.has_uploaded_file,
                "views": video.views,
                "created_at": video.created_at,
                "public_url": f"/{video.profile.user.username}/",
            }
            for video in PortfolioVideo.objects.select_related("profile", "profile__user")
            .order_by("-created_at")[:8]
        ]

        return Response(
            {
                "summary": summary,
                "profiles": serialized_profiles,
                "recent_videos": recent_videos,
            }
        )


class AdminProfileRoleUpdateAPIView(APIView):
    permission_classes = (IsAuthenticatedAdmin,)
    throttle_classes = (SecureOwnerReviewThrottle,)

    @transaction.atomic
    def post(self, request, username):
        profile = get_object_or_404(
            EditorProfile.objects.select_related("user"),
            user__username__iexact=username,
        )
        target_role = str(request.data.get("role", "")).strip()
        valid_roles = {
            AccountRole.ADMIN,
            AccountRole.EDITOR,
            AccountRole.CLIENT,
        }
        if target_role not in valid_roles:
            raise ValidationError({"role": "Choose a valid role."})

        if profile.role == target_role:
            return Response(
                {
                    "ok": True,
                    "message": f"{profile.display_name} is already set to {profile.get_role_display()}.",
                    "profile": serialize_admin_profile(profile),
                    "current_user_can_access_admin": has_admin_role(request.user),
                    "current_user_can_access_django_admin": bool(
                        request.user.is_staff or request.user.is_superuser
                    ),
                    "current_user_role": getattr(
                        getattr(request.user, "editor_profile", None),
                        "role",
                        None,
                    ),
                }
            )

        profile.role = target_role
        profile.save(update_fields=["role", "updated_at"])
        if profile.user_id == request.user.id and hasattr(request.user, "editor_profile"):
            request.user.editor_profile.role = target_role

        return Response(
            {
                "ok": True,
                "message": f"{profile.display_name} is now set to {profile.get_role_display()}.",
                "profile": serialize_admin_profile(profile),
                "current_user_can_access_admin": has_admin_role(request.user),
                "current_user_can_access_django_admin": bool(
                    request.user.is_staff or request.user.is_superuser
                ),
                "current_user_role": getattr(
                    getattr(request.user, "editor_profile", None),
                    "role",
                    None,
                ),
            }
        )


class SecureVideoUploadAPIView(APIView):
    permission_classes = (IsAuthenticatedEditor,)
    throttle_classes = (SecureVideoUploadThrottle,)
    parser_classes = (MultiPartParser, FormParser)

    @transaction.atomic
    def post(self, request):
        serializer = SecureVideoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = request.user.editor_profile
        uploaded_file = serializer.validated_data.pop("uploaded_file")
        video = PortfolioVideo(
            profile=profile,
            sort_order=profile.videos.count(),
            video_source=VideoSourceType.UPLOAD,
            url="",
            **serializer.validated_data,
        )

        try:
            store_secure_video_asset(video, uploaded_file)
            video.save()
        except (CloudinaryError, DatabaseError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        response_data = SecureVideoSerializer(video).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class SecureVideoStreamSessionAPIView(APIView):
    throttle_classes = (SecureVideoStreamThrottle,)

    def get(self, request, video_id):
        video = get_secure_video_or_404(video_id)
        assert_video_is_public_or_owned(video, request)
        if not video.has_uploaded_file and not cloudinary_public_id_for_video(video):
            raise ValidationError({"detail": "This video is not backed by a secure uploaded asset."})

        token, expires_at, watermark_text, viewer_hash = issue_stream_token(request, video)
        record_access_event(
            VideoAccessEventType.STREAM_TOKEN_ISSUED,
            video=video,
            request=request,
            user=request.user if request.user.is_authenticated else None,
            viewer_hash=viewer_hash,
            metadata={"expires_at": expires_at.isoformat()},
        )

        payload = {
            "video": SecureVideoSerializer(video).data,
            "stream_url": build_stream_file_url(request, video, token),
            "expires_at": expires_at,
            "watermark": {
                "enabled": bool(video.watermark_enabled),
                "text": watermark_text,
            },
            "viewer_policy": {
                "download_allowed": False,
                "disable_context_menu": True,
                "disable_picture_in_picture": True,
                "pause_when_hidden": True,
            },
        }
        return Response(StreamSessionSerializer(payload).data)


class SecureVideoStreamFileAPIView(APIView):
    throttle_classes = (SecureVideoStreamThrottle,)

    def get(self, request, video_id):
        token = unquote(request.GET.get("token", "").strip())
        if not token:
            raise PermissionDenied("Missing stream token.")

        payload = verify_stream_token(token, request)
        video = get_secure_video_or_404(video_id)
        assert_video_is_public_or_owned(video, request)
        if str(video.id) != payload.get("video_id"):
            raise PermissionDenied("Stream token does not match this video.")

        watermark_text = payload.get("watermark_text", "")
        file_name = video.original_filename or f"{video.id}.mp4"

        PortfolioVideo.objects.filter(pk=video.pk).update(views=F("views") + 1)
        record_access_event(
            VideoAccessEventType.STREAM_REDIRECTED,
            video=video,
            request=request,
            user=request.user if request.user.is_authenticated else None,
            viewer_hash=payload.get("viewer_hash", ""),
            metadata={"watermark_text": watermark_text},
        )

        if cloudinary_public_id_for_video(video):
            expires_at = timezone.now() + timedelta(seconds=300)
            return proxy_cloudinary_asset(
                build_cloudinary_delivery_url(
                    video,
                    expires_at=expires_at,
                    watermark_text=watermark_text,
                    as_attachment=False,
                ),
                fallback_name=file_name,
                inline=True,
            )

        local_handle = open_local_media_file(video.uploaded_file)
        if local_handle is None:
            raise Http404("Secure asset source is unavailable.")
        from django.http import FileResponse
        import mimetypes

        content_type = mimetypes.guess_type(file_name)[0] or "video/mp4"
        response = FileResponse(local_handle, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{file_name}"'
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class SecureVideoLikeAPIView(APIView):
    throttle_classes = (SecureVideoLikeThrottle,)

    @transaction.atomic
    def post(self, request, video_id):
        video = get_secure_video_or_404(video_id)
        assert_video_is_public_or_owned(video, request)
        viewer_hash = build_viewer_hash(request)
        like, _created = VideoLike.objects.get_or_create(
            video=video,
            viewer_hash=viewer_hash,
            defaults={
                "user": request.user if request.user.is_authenticated else None,
                "ip_address": get_client_ip(request) or None,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                "is_active": True,
            },
        )
        if like.pk and not _created:
            like.is_active = not like.is_active
            if request.user.is_authenticated and like.user_id is None:
                like.user = request.user
            like.save(update_fields=["is_active", "user", "updated_at"])

        record_access_event(
            VideoAccessEventType.LIKE_TOGGLED,
            video=video,
            request=request,
            user=request.user if request.user.is_authenticated else None,
            viewer_hash=viewer_hash,
            metadata={"liked": like.is_active},
        )
        payload = {
            "liked": current_like_state(video, viewer_hash),
            "like_count": like_count(video),
        }
        return Response(PublicVideoLikeStateSerializer(payload).data)


class SecureVideoRatingAPIView(APIView):
    throttle_classes = (SecureVideoRatingThrottle,)

    @transaction.atomic
    def post(self, request, video_id):
        video = get_secure_video_or_404(video_id)
        assert_video_is_public_or_owned(video, request)
        serializer = PublicVideoRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        viewer_hash = build_viewer_hash(request)
        VideoRating.objects.update_or_create(
            video=video,
            viewer_hash=viewer_hash,
            defaults={
                "user": request.user if request.user.is_authenticated else None,
                "ip_address": get_client_ip(request) or None,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                "score": serializer.validated_data["score"],
            },
        )
        average_rating, ratings_count = rating_summary(video)
        record_access_event(
            VideoAccessEventType.RATING_SUBMITTED,
            video=video,
            request=request,
            user=request.user if request.user.is_authenticated else None,
            viewer_hash=viewer_hash,
            metadata={"score": serializer.validated_data["score"]},
        )
        payload = {
            "score": serializer.validated_data["score"],
            "average_rating": average_rating,
            "ratings_count": ratings_count,
        }
        return Response(PublicVideoRatingStateSerializer(payload).data)


class VideoDownloadRequestAPIView(APIView):
    permission_classes = (IsAuthenticatedUser,)
    throttle_classes = (SecureVideoDownloadRequestThrottle,)

    @transaction.atomic
    def post(self, request, video_id):
        video = get_secure_video_or_404(video_id)
        assert_video_is_public_or_owned(video, request)
        if request.user.id == video.profile.user_id:
            raise ValidationError({"detail": "Owners do not need to request their own downloads."})
        if active_download_grant_for(video, request.user):
            raise ValidationError({"detail": "You already have download access for this video."})
        if not video.has_uploaded_file and not cloudinary_public_id_for_video(video):
            raise ValidationError({"detail": "This video is not available for secure download."})

        existing_request = VideoDownloadRequest.objects.filter(
            requester=request.user,
            video=video,
        ).first()
        if (
            existing_request
            and existing_request.status == DownloadRequestStatus.PENDING
            and existing_request.telegram_message_id
        ):
            raise ValidationError({"detail": "Your request is already pending review."})

        serializer = DownloadRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        download_request, _created = VideoDownloadRequest.objects.update_or_create(
            requester=request.user,
            video=video,
            defaults={
                "status": DownloadRequestStatus.PENDING,
                "video_title_snapshot": video.title,
                "video_preview_url_snapshot": video.thumbnail_url,
                "request_message": serializer.validated_data.get("request_message", ""),
                "owner_response_message": "",
                "telegram_message_id": "",
                "telegram_chat_id": video.profile.telegram_chat_id,
                "reviewed_at": None,
                "approved_at": None,
                "reviewed_by": None,
            },
        )
        delivery_result = notify_owner_about_download_request(download_request, request)
        record_access_event(
            VideoAccessEventType.DOWNLOAD_REQUESTED,
            video=video,
            request=request,
            user=request.user,
            download_request=download_request,
            metadata={
                "status": download_request.status,
                "delivery_status": (delivery_result or {}).get("delivery_status", ""),
                "delivery_confirmed": bool((delivery_result or {}).get("delivery_confirmed")),
            },
        )
        response_payload = VideoDownloadRequestSerializer(download_request).data
        response_payload.update(delivery_result or {})
        return Response(
            response_payload,
            status=status.HTTP_201_CREATED,
        )


class OwnerDownloadRequestListAPIView(APIView):
    permission_classes = (IsAuthenticatedEditorOrAdmin,)
    throttle_classes = (SecureOwnerNotificationsThrottle,)

    def get(self, request):
        queryset = VideoDownloadRequest.objects.select_related(
            "video",
            "video__profile",
            "video__profile__user",
            "requester",
            "reviewed_by",
            "download_grant",
        )
        if not has_admin_role(request.user):
            queryset = queryset.filter(video__profile__user=request.user)
        status_filter = request.GET.get("status", "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        serializer = VideoDownloadRequestSerializer(queryset, many=True)
        return Response(serializer.data)


class OwnerDownloadRequestReviewAPIView(APIView):
    permission_classes = (IsAuthenticatedEditorOrAdmin,)
    throttle_classes = (SecureOwnerReviewThrottle,)

    @transaction.atomic
    def post(self, request, request_id):
        download_request = get_object_or_404(
            VideoDownloadRequest.objects.select_related(
                "video",
                "video__profile",
                "video__profile__user",
                "requester",
                "download_grant",
            ),
            pk=request_id,
        )
        is_owner = download_request.video.profile.user_id == request.user.id
        if not (is_owner or has_admin_role(request.user)):
            raise PermissionDenied("Only the video owner or an admin can review this request.")

        serializer = DownloadRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        download_request.status = serializer.validated_data["status"]
        download_request.owner_response_message = serializer.validated_data.get(
            "owner_response_message", ""
        )
        download_request.reviewed_at = timezone.now()
        download_request.reviewed_by = request.user
        download_request.approved_at = (
            timezone.now() if download_request.status == DownloadRequestStatus.APPROVED else None
        )
        download_request.save(
            update_fields=[
                "status",
                "owner_response_message",
                "reviewed_at",
                "reviewed_by",
                "approved_at",
            ]
        )
        if download_request.status == DownloadRequestStatus.APPROVED:
            grant_download_access(download_request, reviewer=request.user)
        else:
            revoke_download_access(download_request)
        notify_requester_about_download_decision(download_request)

        event_type = (
            VideoAccessEventType.DOWNLOAD_APPROVED
            if download_request.status == DownloadRequestStatus.APPROVED
            else VideoAccessEventType.DOWNLOAD_REJECTED
        )
        record_access_event(
            event_type,
            video=download_request.video,
            request=request,
            user=request.user,
            download_request=download_request,
            metadata={"status": download_request.status},
        )
        return Response(VideoDownloadRequestSerializer(download_request).data)


class SecureVideoDownloadLinkAPIView(APIView):
    permission_classes = (IsAuthenticatedUser,)
    throttle_classes = (SecureVideoDownloadLinkThrottle,)

    def get(self, request, video_id):
        video = get_secure_video_or_404(video_id)
        if not user_can_download_video(request.user, video):
            raise PermissionDenied("This user does not have approved download access for the video.")
        download_grant = active_download_grant_for(video, request.user)
        download_request = download_grant.source_request if download_grant else None

        token, expires_at = issue_download_token(request.user, video, download_request)
        record_access_event(
            VideoAccessEventType.DOWNLOAD_LINK_ISSUED,
            video=video,
            request=request,
            user=request.user,
            download_request=download_request,
            metadata={"expires_at": expires_at.isoformat()},
        )
        payload = {
            "download_url": build_download_file_url(request, video, token),
            "expires_at": expires_at,
        }
        return Response(DownloadLinkSerializer(payload).data)


class SecureVideoDownloadFileAPIView(APIView):
    permission_classes = (IsAuthenticatedUser,)
    throttle_classes = (SecureVideoDownloadLinkThrottle,)

    def get(self, request, video_id):
        token = unquote(request.GET.get("token", "").strip())
        if not token:
            raise PermissionDenied("Missing download token.")

        payload = verify_download_token(token, request)
        video = get_secure_video_or_404(video_id)
        if str(video.id) != payload.get("video_id"):
            raise PermissionDenied("Download token does not match this video.")

        if not user_can_download_video(request.user, video):
            raise PermissionDenied("This user does not have approved download access for the video.")

        download_grant = active_download_grant_for(video, request.user)
        download_request = download_grant.source_request if download_grant else None
        if download_request and payload.get("download_request_id") != download_request.id:
                raise PermissionDenied("Download token does not match the approved request.")

        file_name = video.original_filename or f"{video.id}.mp4"
        record_access_event(
            VideoAccessEventType.DOWNLOAD_REDIRECTED,
            video=video,
            request=request,
            user=request.user,
            download_request=download_request,
            metadata={"file_name": file_name},
        )

        if cloudinary_public_id_for_video(video):
            upstream_url = build_cloudinary_delivery_url(
                video,
                expires_at=timezone.now() + timedelta(seconds=30),
                as_attachment=True,
            )
            return proxy_cloudinary_asset(upstream_url, fallback_name=file_name, inline=False)

        local_handle = open_local_media_file(video.uploaded_file)
        if local_handle is None:
            raise Http404("Secure asset source is unavailable.")
        from django.http import FileResponse
        import mimetypes

        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        response = FileResponse(local_handle, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class OwnerNotificationListAPIView(APIView):
    permission_classes = (IsAuthenticatedEditorOrAdmin,)
    throttle_classes = (SecureOwnerNotificationsThrottle,)

    def get(self, request):
        queryset = OwnerNotification.objects.select_related("video", "download_request", "owner")
        if not has_admin_role(request.user):
            queryset = queryset.filter(owner=request.user)
        unread_only = request.GET.get("unread", "").strip().lower() in {"1", "true", "yes"}
        if unread_only:
            queryset = queryset.filter(is_read=False)
        serializer = OwnerNotificationSerializer(queryset, many=True)
        return Response(serializer.data)


class OwnerNotificationReadAPIView(APIView):
    permission_classes = (IsAuthenticatedEditorOrAdmin,)
    throttle_classes = (SecureOwnerNotificationsThrottle,)

    @transaction.atomic
    def post(self, request, notification_id):
        queryset = OwnerNotification.objects.all()
        if not has_admin_role(request.user):
            queryset = queryset.filter(owner=request.user)
        notification = get_object_or_404(queryset, pk=notification_id)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        return Response(OwnerNotificationSerializer(notification).data)
