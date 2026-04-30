import uuid
from urllib.parse import quote

from django.contrib.auth.models import User
from django.db import models


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


class VideoSourceType(models.TextChoices):
    LINK = "link", "Link"
    UPLOAD = "upload", "Upload"
    BOTH = "both", "Both"


def portfolio_video_upload_to(instance, filename):
    return f"portfolio_videos/{instance.profile.user.username}/{instance.id}/{filename}"


class EditorProfile(models.Model):
    default_bio = "Video editor on Ela-sam Portfolio Show."

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="editor_profile",
    )
    bio = models.TextField(blank=True, default=default_bio)
    avatar_url = models.URLField(max_length=500, blank=True)
    telegram = models.CharField(max_length=64, blank=True)
    whatsapp = models.CharField(max_length=32, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return self.user.username

    @staticmethod
    def build_default_avatar_url(username):
        return f"https://picsum.photos/seed/{quote(username)}/200/200.jpg"

    @property
    def avatar(self):
        return self.avatar_url or self.build_default_avatar_url(self.user.username)

    def has_contact_method(self):
        return any([self.user.email, self.telegram, self.whatsapp, self.phone])


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
    uploaded_file = models.FileField(
        upload_to=portfolio_video_upload_to,
        blank=True,
    )
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
