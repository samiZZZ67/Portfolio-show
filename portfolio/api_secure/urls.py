from django.urls import path

from .views import (
    OwnerDownloadRequestListAPIView,
    OwnerDownloadRequestReviewAPIView,
    OwnerNotificationListAPIView,
    OwnerNotificationReadAPIView,
    SecureVideoDownloadFileAPIView,
    SecureVideoDownloadLinkAPIView,
    SecureVideoLikeAPIView,
    SecureVideoRatingAPIView,
    SecureVideoStreamFileAPIView,
    SecureVideoStreamSessionAPIView,
    SecureVideoUploadAPIView,
    VideoDownloadRequestAPIView,
)

urlpatterns = [
    path("videos/upload/", SecureVideoUploadAPIView.as_view(), name="secure-video-upload"),
    path("videos/<uuid:video_id>/stream/", SecureVideoStreamSessionAPIView.as_view(), name="secure-video-stream"),
    path("videos/<uuid:video_id>/stream/file/", SecureVideoStreamFileAPIView.as_view(), name="secure-video-stream-file"),
    path("videos/<uuid:video_id>/like/", SecureVideoLikeAPIView.as_view(), name="secure-video-like"),
    path("videos/<uuid:video_id>/rate/", SecureVideoRatingAPIView.as_view(), name="secure-video-rate"),
    path("videos/<uuid:video_id>/download-request/", VideoDownloadRequestAPIView.as_view(), name="secure-video-download-request"),
    path("videos/<uuid:video_id>/download/", SecureVideoDownloadLinkAPIView.as_view(), name="secure-video-download"),
    path("videos/<uuid:video_id>/download/file/", SecureVideoDownloadFileAPIView.as_view(), name="secure-video-download-file"),
    path("download-requests/", OwnerDownloadRequestListAPIView.as_view(), name="secure-owner-download-requests"),
    path("download-requests/<int:request_id>/review/", OwnerDownloadRequestReviewAPIView.as_view(), name="secure-owner-download-review"),
    path("notifications/", OwnerNotificationListAPIView.as_view(), name="secure-owner-notifications"),
    path("notifications/<int:notification_id>/read/", OwnerNotificationReadAPIView.as_view(), name="secure-owner-notification-read"),
]
