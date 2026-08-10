from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from portfolio.models import (
    DownloadRequestStatus,
    OwnerNotification,
    PortfolioVideo,
    VideoDownloadRequest,
    VideoLike,
    VideoPlatform,
    VideoRating,
)


class SecureVideoSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source="profile.user.username", read_only=True)
    like_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    aspect_ratio = serializers.CharField(read_only=True)

    class Meta:
        model = PortfolioVideo
        fields = (
            "id",
            "title",
            "owner_username",
            "platform",
            "content_type",
            "category",
            "duration",
            "thumbnail_url",
            "views",
            "watermark_enabled",
            "original_filename",
            "original_format",
            "original_width",
            "original_height",
            "original_bitrate",
            "original_file_size",
            "frame_rate",
            "aspect_ratio",
            "like_count",
            "average_rating",
            "ratings_count",
            "created_at",
            "updated_at",
        )

    def get_like_count(self, obj):
        return obj.public_likes.filter(is_active=True).count()

    def get_average_rating(self, obj):
        ratings = obj.public_ratings.all()
        if not ratings:
            return 0.0
        return round(sum(rating.score for rating in ratings) / len(ratings), 1)

    def get_ratings_count(self, obj):
        return obj.public_ratings.count()


class SecureVideoUploadSerializer(serializers.ModelSerializer):
    uploaded_file = serializers.FileField(write_only=True)

    class Meta:
        model = PortfolioVideo
        fields = (
            "title",
            "uploaded_file",
            "platform",
            "content_type",
            "category",
            "duration",
            "thumbnail_url",
            "original_width",
            "original_height",
            "original_bitrate",
            "frame_rate",
            "watermark_enabled",
        )

    def validate_platform(self, value):
        return value or VideoPlatform.OTHER


class PublicVideoRatingSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)


class DownloadRequestCreateSerializer(serializers.Serializer):
    request_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class DownloadRequestReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(
            DownloadRequestStatus.APPROVED,
            DownloadRequestStatus.REJECTED,
        )
    )
    owner_response_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class VideoDownloadRequestSerializer(serializers.ModelSerializer):
    requester_username = serializers.CharField(source="requester.username", read_only=True)
    owner_username = serializers.CharField(source="video.profile.user.username", read_only=True)
    video_title = serializers.CharField(source="video.title", read_only=True)
    reviewed_by_username = serializers.CharField(source="reviewed_by.username", read_only=True)
    download_granted = serializers.SerializerMethodField()

    class Meta:
        model = VideoDownloadRequest
        fields = (
            "id",
            "video",
            "video_title",
            "video_title_snapshot",
            "video_preview_url_snapshot",
            "requester",
            "requester_username",
            "owner_username",
            "status",
            "request_message",
            "owner_response_message",
            "reviewed_by_username",
            "download_granted",
            "requested_at",
            "reviewed_at",
            "approved_at",
        )
        read_only_fields = fields

    def get_download_granted(self, obj):
        try:
            grant = obj.download_grant
        except ObjectDoesNotExist:
            return False
        return bool(grant.is_active and grant.revoked_at is None)


class OwnerNotificationSerializer(serializers.ModelSerializer):
    video_title = serializers.CharField(source="video.title", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = OwnerNotification
        fields = (
            "id",
            "owner_username",
            "notification_type",
            "video",
            "video_title",
            "download_request",
            "title",
            "message",
            "payload",
            "is_read",
            "created_at",
            "read_at",
        )


class PublicVideoLikeStateSerializer(serializers.Serializer):
    liked = serializers.BooleanField()
    like_count = serializers.IntegerField()


class PublicVideoRatingStateSerializer(serializers.Serializer):
    score = serializers.IntegerField()
    average_rating = serializers.FloatField()
    ratings_count = serializers.IntegerField()


class StreamSessionSerializer(serializers.Serializer):
    video = serializers.DictField()
    stream_url = serializers.URLField()
    expires_at = serializers.DateTimeField()
    watermark = serializers.DictField()
    viewer_policy = serializers.DictField()


class DownloadLinkSerializer(serializers.Serializer):
    download_url = serializers.URLField()
    expires_at = serializers.DateTimeField()
