import uuid
from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.files.storage import Storage, default_storage
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify


class VideoContentType(models.TextChoices):
    SHORT = "short", "Short Content"
    LONG = "long", "Long Content"


class VideoCategory(models.TextChoices):
    COMMERCIAL_ADS = "Commercial / Ads", "Commercial / Ads"
    WEDDING = "Wedding", "Wedding"
    YOUTUBE_CONTENT = "YouTube Content", "YouTube Content"
    DOCUMENTARY = "Documentary", "Documentary"
    MUSIC_VIDEO = "Music Video", "Music Video"
    SOCIAL_MEDIA = "Social Media", "Social Media"
    CORPORATE = "Corporate", "Corporate"


class AccountRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    EDITOR = "editor", "Editor"
    CLIENT = "client", "Client"


class VideoSourceType(models.TextChoices):
    LINK = "link", "Link"
    UPLOAD = "upload", "Upload"
    BOTH = "both", "Both"


class VideoPlatform(models.TextChoices):
    TIKTOK = "tiktok", "TikTok (9:16)"
    YOUTUBE = "youtube", "YouTube (16:9)"
    INSTAGRAM = "instagram", "Instagram / Reels"
    FACEBOOK = "facebook", "Facebook"
    OTHER = "other", "Other"


class VideoReactionType(models.TextChoices):
    STAR = "star", "Star"
    LIKE = "like", "Like"
    LOVE = "love", "Love"
    FIRE = "fire", "Fire"


class DownloadRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class OwnerNotificationType(models.TextChoices):
    DOWNLOAD_REQUEST = "download_request", "Download request"
    DOWNLOAD_APPROVED = "download_approved", "Download approved"
    DOWNLOAD_REJECTED = "download_rejected", "Download rejected"


class VideoAccessEventType(models.TextChoices):
    STREAM_TOKEN_ISSUED = "stream_token_issued", "Stream token issued"
    STREAM_REDIRECTED = "stream_redirected", "Stream redirected"
    LIKE_TOGGLED = "like_toggled", "Like toggled"
    RATING_SUBMITTED = "rating_submitted", "Rating submitted"
    DOWNLOAD_REQUESTED = "download_requested", "Download requested"
    DOWNLOAD_APPROVED = "download_approved", "Download approved"
    DOWNLOAD_REJECTED = "download_rejected", "Download rejected"
    DOWNLOAD_LINK_ISSUED = "download_link_issued", "Download link issued"
    DOWNLOAD_REDIRECTED = "download_redirected", "Download redirected"


def profile_avatar_upload_to(instance, filename):
    normalized_filename = compact_upload_filename(filename, default_stem="avatar", max_stem_length=20)
    return f"a/{instance.user_id}/{normalized_filename}"


def portfolio_video_upload_to(instance, filename):
    normalized_filename = compact_upload_filename(filename, default_stem="video", max_stem_length=24)
    return f"v/{instance.profile_id}/{instance.id.hex[:12]}-{normalized_filename}"


def compact_upload_filename(filename, default_stem="file", max_stem_length=24):
    path = PurePosixPath(str(filename))
    suffix = path.suffix.lower()[:10]
    raw_stem = path.stem
    normalized_stem = slugify(raw_stem).strip("-_") or default_stem
    return f"{normalized_stem[:max_stem_length]}{suffix}"


@deconstructible
class PortfolioVideoStorage(Storage):
    """
    Uses Cloudinary's video storage when media storage is enabled and
    falls back to Django's default storage everywhere else.
    """

    def _get_storage(self):
        if getattr(settings, "CLOUDINARY_MEDIA_ENABLED", False):
            from cloudinary_storage.storage import VideoMediaCloudinaryStorage

            return VideoMediaCloudinaryStorage()
        return default_storage

    def _open(self, name, mode="rb"):
        return self._get_storage()._open(name, mode)

    def _save(self, name, content):
        return self._get_storage()._save(name, content)

    def delete(self, name):
        return self._get_storage().delete(name)

    def exists(self, name):
        return self._get_storage().exists(name)

    def listdir(self, path):
        return self._get_storage().listdir(path)

    def size(self, name):
        return self._get_storage().size(name)

    def url(self, name):
        return self._get_storage().url(name)

    def get_available_name(self, name, max_length=None):
        return self._get_storage().get_available_name(name, max_length=max_length)


class EditorProfile(models.Model):
    default_bio = "Video editor on Ela-sam Portfolio Show."

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="editor_profile",
    )
    role = models.CharField(
        max_length=10,
        choices=AccountRole.choices,
        default=AccountRole.EDITOR,
    )
    cname = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True, default=default_bio)
    avatar_file = models.FileField(upload_to=profile_avatar_upload_to, blank=True, max_length=500)
    avatar_url = models.URLField(max_length=500, blank=True)
    telegram = models.CharField(max_length=64, blank=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True)
    whatsapp = models.CharField(max_length=32, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    other_contacts = models.JSONField(default=list, blank=True)
    clients_served = models.PositiveIntegerField(default=0)
    completed_projects = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["telegram"],
                condition=~models.Q(telegram=""),
                name="unique_nonblank_editorprofile_telegram",
            ),
            models.UniqueConstraint(
                fields=["telegram_chat_id"],
                condition=~models.Q(telegram_chat_id=""),
                name="unique_nonblank_editorprofile_telegram_chat_id",
            ),
        ]

    def __str__(self):
        return self.user.username

    @staticmethod
    def build_default_avatar_url(username):
        return f"https://picsum.photos/seed/{quote(username)}/200/200.jpg"

    @property
    def avatar(self):
        if self.avatar_file:
            return self.avatar_file.url
        return self.avatar_url or self.build_default_avatar_url(self.user.username)

    @property
    def display_name(self):
        return self.cname or self.user.username

    @property
    def is_admin(self):
        return self.role == AccountRole.ADMIN

    @property
    def is_editor(self):
        return self.role == AccountRole.EDITOR

    @property
    def is_client(self):
        return self.role == AccountRole.CLIENT

    @property
    def has_custom_avatar(self):
        return bool(self.avatar_file or self.avatar_url)

    def has_contact_method(self):
        return any([self.user.email, self.telegram, self.whatsapp, self.phone, self.other_contacts])

    @property
    def has_telegram_binding(self):
        return bool(self.telegram or self.telegram_chat_id)

    @property
    def is_public_profile(self):
        return self.is_editor or (self.is_client and self.has_contact_method())

    def setup_state(self):
        return {
            "needs_avatar": not self.has_custom_avatar,
            "needs_contact": not self.has_contact_method(),
            "needs_video": self.is_editor and not self.videos.exists(),
        }


class SkillTag(models.Model):
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name).strip("-_") or "skill"
            candidate = base_slug[:64]
            suffix = 2
            while SkillTag.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                suffix_text = f"-{suffix}"
                candidate = f"{base_slug[: max(1, 64 - len(suffix_text))]}{suffix_text}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class EditorSkill(models.Model):
    profile = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    skill = models.ForeignKey(
        SkillTag,
        on_delete=models.CASCADE,
        related_name="editors",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "skill"],
                name="unique_editor_skill",
            )
        ]
        ordering = ["skill__sort_order", "skill__name"]

    def __str__(self):
        return f"{self.profile.user.username}: {self.skill.name}"


class PortfolioVideo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    title = models.CharField(max_length=255)
    url = models.URLField(max_length=500, blank=True)
    video_source = models.CharField(
        max_length=10,
        choices=VideoSourceType.choices,
        default=VideoSourceType.LINK,
    )
    platform = models.CharField(
        max_length=20,
        choices=VideoPlatform.choices,
        default=VideoPlatform.OTHER,
    )
    uploaded_file = models.FileField(
        upload_to=portfolio_video_upload_to,
        blank=True,
        max_length=500,
        storage=PortfolioVideoStorage(),
    )
    storage_public_id = models.CharField(max_length=500, blank=True, db_index=True)
    original_filename = models.CharField(max_length=255, blank=True)
    original_format = models.CharField(max_length=32, blank=True)
    original_width = models.PositiveIntegerField(null=True, blank=True)
    original_height = models.PositiveIntegerField(null=True, blank=True)
    original_bitrate = models.PositiveIntegerField(null=True, blank=True)
    original_file_size = models.PositiveBigIntegerField(null=True, blank=True)
    frame_rate = models.CharField(max_length=32, blank=True)
    watermark_enabled = models.BooleanField(default=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    content_type = models.CharField(
        max_length=5,
        choices=VideoContentType.choices,
    )
    category = models.CharField(
        max_length=32,
        choices=VideoCategory.choices,
    )
    duration = models.CharField(max_length=20, blank=True)
    views = models.PositiveBigIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.profile.user.username}: {self.title}"

    @property
    def playback_url(self):
        if self.uploaded_file:
            return self.uploaded_file.url
        return self.url

    @property
    def has_uploaded_file(self):
        return bool(self.uploaded_file)

    @property
    def secure_public_id(self):
        return self.storage_public_id or (self.uploaded_file.name if self.uploaded_file else "")

    @property
    def aspect_ratio(self):
        if self.original_width and self.original_height:
            return f"{self.original_width}:{self.original_height}"
        return ""

    def save(self, *args, **kwargs):
        if not self.duration:
            self.duration = "0:30" if self.content_type == VideoContentType.SHORT else "5:00"
        if not self.thumbnail_url:
            size = "300/530" if self.content_type == VideoContentType.SHORT else "400/225"
            self.thumbnail_url = f"https://picsum.photos/seed/{self.id.hex}/{size}.jpg"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        uploaded_file = self.uploaded_file
        super().delete(*args, **kwargs)
        if uploaded_file:
            uploaded_file.delete(save=False)


class FollowRelationship(models.Model):
    follower = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="following_relationships",
    )
    followed = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="follower_relationships",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "followed"],
                name="unique_follow_relationship",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower.user.username} -> {self.followed.user.username}"


class VideoReaction(models.Model):
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    profile = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="video_reactions",
    )
    reaction_type = models.CharField(
        max_length=10,
        choices=VideoReactionType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "profile", "reaction_type"],
                name="unique_video_reaction_per_type",
            )
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.profile.user.username} {self.reaction_type} {self.video_id}"


class VideoStarRating(models.Model):
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    profile = models.ForeignKey(
        EditorProfile,
        on_delete=models.CASCADE,
        related_name="video_ratings",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "profile"],
                name="unique_video_star_rating",
            )
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.profile.user.username} rated {self.video_id} as {self.rating}"


class VideoLike(models.Model):
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="public_likes",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="video_likes",
        null=True,
        blank=True,
    )
    viewer_hash = models.CharField(max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "viewer_hash"],
                name="unique_public_video_like",
            )
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Like<{self.video_id}:{self.viewer_hash[:8]}>"


class VideoRating(models.Model):
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="public_ratings",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="video_ratings_public",
        null=True,
        blank=True,
    )
    viewer_hash = models.CharField(max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["video", "viewer_hash"],
                name="unique_public_video_rating",
            )
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Rating<{self.video_id}:{self.score}>"


class VideoDownloadRequest(models.Model):
    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_download_requests",
    )
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="download_requests",
    )
    status = models.CharField(
        max_length=12,
        choices=DownloadRequestStatus.choices,
        default=DownloadRequestStatus.PENDING,
        db_index=True,
    )
    video_title_snapshot = models.CharField(max_length=255, blank=True)
    video_preview_url_snapshot = models.URLField(max_length=500, blank=True)
    request_message = models.TextField(blank=True)
    owner_response_message = models.TextField(blank=True)
    telegram_message_id = models.CharField(max_length=64, blank=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_video_download_requests",
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "video"],
                name="unique_video_download_request_per_user",
            )
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.requester.username} -> {self.video_id} ({self.status})"


class VideoDownloadGrant(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_download_grants",
    )
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="download_grants",
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="granted_video_downloads",
        null=True,
        blank=True,
    )
    source_request = models.OneToOneField(
        VideoDownloadRequest,
        on_delete=models.SET_NULL,
        related_name="download_grant",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "video"],
                condition=models.Q(is_active=True),
                name="unique_active_video_download_grant",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} -> {self.video_id} ({'active' if self.is_active else 'revoked'})"


class OwnerNotification(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owner_notifications",
    )
    notification_type = models.CharField(
        max_length=32,
        choices=OwnerNotificationType.choices,
    )
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="owner_notifications",
    )
    download_request = models.ForeignKey(
        VideoDownloadRequest,
        on_delete=models.CASCADE,
        related_name="owner_notifications",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.owner.username}: {self.title}"


class VideoAccessLog(models.Model):
    video = models.ForeignKey(
        PortfolioVideo,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    actor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="video_access_logs",
        null=True,
        blank=True,
    )
    download_request = models.ForeignKey(
        VideoDownloadRequest,
        on_delete=models.SET_NULL,
        related_name="access_logs",
        null=True,
        blank=True,
    )
    event_type = models.CharField(
        max_length=32,
        choices=VideoAccessEventType.choices,
    )
    viewer_hash = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.video_id}:{self.event_type}"
