from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.contrib.admin.exceptions import NotRegistered
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AccountRole,
    EditorSkill,
    EditorProfile,
    FollowRelationship,
    PortfolioVideo,
    SkillTag,
    VideoDownloadGrant,
    VideoDownloadRequest,
    VideoReaction,
    VideoStarRating,
)

admin.site.site_header = "Ela-sam Admin"
admin.site.site_title = "Ela-sam Admin"
admin.site.index_title = "Portfolio control center"

try:
    admin.site.unregister(User)
except NotRegistered:
    pass


def contact_query():
    return (
        Q(user__email__gt="")
        | Q(telegram__gt="")
        | Q(whatsapp__gt="")
        | Q(phone__gt="")
        | ~Q(other_contacts=[])
    )


def admin_video_destination(video):
    if video.has_uploaded_file:
        return reverse(
            "portfolio:video-stream",
            kwargs={"username": video.profile.user.username, "video_id": video.pk},
        )
    return video.url


class PublicProfileListFilter(admin.SimpleListFilter):
    title = "public status"
    parameter_name = "public_status"

    def lookups(self, request, model_admin):
        return (
            ("public", "Public"),
            ("private", "Private"),
        )

    def queryset(self, request, queryset):
        public_filter = Q(role=AccountRole.EDITOR) | contact_query()
        if self.value() == "public":
            return queryset.filter(public_filter).distinct()
        if self.value() == "private":
            return queryset.exclude(public_filter).distinct()
        return queryset


class HasCustomAvatarListFilter(admin.SimpleListFilter):
    title = "custom avatar"
    parameter_name = "has_avatar"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        avatar_filter = Q(avatar_file__gt="") | Q(avatar_url__gt="")
        if self.value() == "yes":
            return queryset.filter(avatar_filter)
        if self.value() == "no":
            return queryset.exclude(avatar_filter)
        return queryset


class HasVideosListFilter(admin.SimpleListFilter):
    title = "videos"
    parameter_name = "has_videos"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has videos"),
            ("no", "No videos"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(videos__isnull=False).distinct()
        if self.value() == "no":
            return queryset.filter(videos__isnull=True)
        return queryset


class UploadAvailabilityListFilter(admin.SimpleListFilter):
    title = "uploaded file"
    parameter_name = "has_upload"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Has uploaded file"),
            ("no", "No uploaded file"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(uploaded_file__gt="")
        if self.value() == "no":
            return queryset.exclude(uploaded_file__gt="")
        return queryset


class ProfileRoleListFilter(admin.SimpleListFilter):
    title = "portfolio role"
    parameter_name = "portfolio_role"

    def lookups(self, request, model_admin):
        return AccountRole.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(editor_profile__role=self.value())
        return queryset


class EditorProfileInline(admin.StackedInline):
    model = EditorProfile
    can_delete = False
    extra = 0
    verbose_name_plural = "Portfolio profile"
    fields = (
        "role",
        "cname",
        "bio",
        "avatar_file",
        "avatar_url",
        "telegram",
        "telegram_chat_id",
        "whatsapp",
        "phone",
        "clients_served",
        "completed_projects",
        "public_profile_link",
        "setup_summary",
    )
    readonly_fields = ("public_profile_link", "setup_summary")

    @admin.display(description="Public page")
    def public_profile_link(self, obj):
        if not obj or not obj.pk:
            return "Profile will be created after saving this user."
        url = reverse("portfolio:public-profile", kwargs={"username": obj.user.username})
        return format_html('<a href="{}" target="_blank" rel="noreferrer">Open public profile</a>', url)

    @admin.display(description="Setup status")
    def setup_summary(self, obj):
        if not obj or not obj.pk:
            return "Profile setup starts after the user is saved."
        state = obj.setup_state()
        remaining = [label for label, missing in (
            ("avatar", state["needs_avatar"]),
            ("contact", state["needs_contact"]),
            ("video", state["needs_video"]),
        ) if missing]
        if not remaining:
            return "Complete"
        return f"Needs: {', '.join(remaining)}"


@admin.register(User)
class PortfolioUserAdmin(UserAdmin):
    inlines = (EditorProfileInline,)
    list_display = (
        "username",
        "email",
        "portfolio_role",
        "portfolio_display_name",
        "portfolio_public_status",
        "is_staff",
        "is_active",
        "last_login",
    )
    list_filter = UserAdmin.list_filter + (ProfileRoleListFilter,)
    search_fields = (
        "username",
        "email",
        "editor_profile__cname",
        "editor_profile__telegram",
        "editor_profile__whatsapp",
        "editor_profile__phone",
    )
    list_select_related = ("editor_profile",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("editor_profile")

    @admin.display(description="Role", ordering="editor_profile__role")
    def portfolio_role(self, obj):
        return getattr(obj.editor_profile, "get_role_display", lambda: "No profile")()

    @admin.display(description="Display name", ordering="editor_profile__cname")
    def portfolio_display_name(self, obj):
        profile = getattr(obj, "editor_profile", None)
        return profile.display_name if profile else obj.username

    @admin.display(boolean=True, description="Public")
    def portfolio_public_status(self, obj):
        profile = getattr(obj, "editor_profile", None)
        return bool(profile and profile.is_public_profile)


class PortfolioVideoInline(admin.TabularInline):
    model = PortfolioVideo
    extra = 0
    fields = (
        "title",
        "video_source",
        "content_type",
        "category",
        "views",
        "sort_order",
        "admin_preview",
    )
    readonly_fields = ("admin_preview",)
    show_change_link = True

    @admin.display(description="Preview")
    def admin_preview(self, obj):
        if not obj.pk:
            return "Save the profile first."
        preview_url = admin_video_destination(obj)
        if not preview_url:
            return "No preview available."
        return format_html('<a href="{}" target="_blank" rel="noreferrer">Open video</a>', preview_url)


class EditorSkillInline(admin.TabularInline):
    model = EditorSkill
    extra = 1
    autocomplete_fields = ("skill",)


@admin.register(EditorProfile)
class EditorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "avatar_chip",
        "username_link",
        "display_name",
        "role_badge",
        "public_status",
        "video_total",
        "followers_total",
        "following_total",
        "updated_at",
    )
    list_filter = (
        "role",
        PublicProfileListFilter,
        HasCustomAvatarListFilter,
        HasVideosListFilter,
    )
    search_fields = (
        "user__username",
        "user__email",
        "cname",
        "bio",
        "telegram",
        "whatsapp",
        "phone",
    )
    search_help_text = "Search by username, email, company name, bio, or contact details."
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = (
        "display_name_preview",
        "avatar_preview",
        "public_profile_link",
        "contact_summary",
        "setup_summary",
        "created_at",
        "updated_at",
    )
    inlines = (PortfolioVideoInline, EditorSkillInline)
    actions = ("make_selected_admins", "make_selected_editors", "make_selected_clients")
    list_per_page = 25

    fieldsets = (
        (
            "Account",
            {
                "fields": (
                    "user",
                    "role",
                    "cname",
                    "display_name_preview",
                    "public_profile_link",
                )
            },
        ),
        (
            "Profile Content",
            {
                "fields": (
                    "bio",
                    "avatar_file",
                    "avatar_url",
                    "avatar_preview",
                    "setup_summary",
                )
            },
        ),
        (
            "Contact & Business",
            {
                "fields": (
                    "telegram",
                    "whatsapp",
                    "phone",
                    "other_contacts",
                    "contact_summary",
                    "clients_served",
                    "completed_projects",
                )
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("user").annotate(
            video_total_count=Count("videos", distinct=True),
            follower_total_count=Count("follower_relationships", distinct=True),
            following_total_count=Count("following_relationships", distinct=True),
        )

    @admin.action(description="Change selected profiles to admins")
    def make_selected_admins(self, request, queryset):
        updated = queryset.update(role=AccountRole.ADMIN)
        self.message_user(request, f"{updated} profile(s) changed to admin.")

    @admin.action(description="Change selected profiles to editors")
    def make_selected_editors(self, request, queryset):
        updated = queryset.update(role=AccountRole.EDITOR)
        self.message_user(request, f"{updated} profile(s) changed to editor.")

    @admin.action(description="Change selected profiles to clients")
    def make_selected_clients(self, request, queryset):
        updated = queryset.update(role=AccountRole.CLIENT)
        self.message_user(request, f"{updated} profile(s) changed to client.")

    @admin.display(description="Avatar")
    def avatar_chip(self, obj):
        return format_html(
            '<img src="{}" alt="{}" style="width:40px;height:40px;border-radius:999px;object-fit:cover;border:1px solid #d1d5db;">',
            obj.avatar,
            obj.display_name,
        )

    @admin.display(description="Username", ordering="user__username")
    def username_link(self, obj):
        url = reverse("admin:portfolio_editorprofile_change", args=[obj.pk])
        return format_html('<a href="{}">@{}</a>', url, obj.user.username)

    @admin.display(description="Role", ordering="role")
    def role_badge(self, obj):
        if obj.role == AccountRole.ADMIN:
            color = "#153e75"
            background = "#e6f0ff"
        elif obj.role == AccountRole.EDITOR:
            color = "#176b3a"
            background = "#e7f7ed"
        else:
            color = "#7a3e00"
            background = "#fff3e6"
        return format_html(
            '<span style="display:inline-block;padding:0.25rem 0.6rem;border-radius:999px;background:{};color:{};font-weight:600;">{}</span>',
            background,
            color,
            obj.get_role_display(),
        )

    @admin.display(boolean=True, description="Public")
    def public_status(self, obj):
        return obj.is_public_profile

    @admin.display(description="Videos", ordering="video_total_count")
    def video_total(self, obj):
        return getattr(obj, "video_total_count", 0)

    @admin.display(description="Followers", ordering="follower_total_count")
    def followers_total(self, obj):
        return getattr(obj, "follower_total_count", 0)

    @admin.display(description="Following", ordering="following_total_count")
    def following_total(self, obj):
        return getattr(obj, "following_total_count", 0)

    @admin.display(description="Display name")
    def display_name_preview(self, obj):
        return obj.display_name

    @admin.display(description="Avatar preview")
    def avatar_preview(self, obj):
        return format_html(
            '<img src="{}" alt="{}" style="width:96px;height:96px;border-radius:16px;object-fit:cover;border:1px solid #d1d5db;">',
            obj.avatar,
            obj.display_name,
        )

    @admin.display(description="Public profile")
    def public_profile_link(self, obj):
        url = reverse("portfolio:public-profile", kwargs={"username": obj.user.username})
        return format_html('<a href="{}" target="_blank" rel="noreferrer">Open public portfolio</a>', url)

    @admin.display(description="Contact summary")
    def contact_summary(self, obj):
        details = [
            obj.user.email,
            obj.telegram,
            obj.whatsapp,
            obj.phone,
        ]
        details.extend(item.get("label", "") for item in (obj.other_contacts or []))
        filtered = [item for item in details if item]
        return ", ".join(filtered) if filtered else "No contact methods added yet."

    @admin.display(description="Setup status")
    def setup_summary(self, obj):
        state = obj.setup_state()
        remaining = [label for label, missing in (
            ("avatar", state["needs_avatar"]),
            ("contact", state["needs_contact"]),
            ("video", state["needs_video"]),
        ) if missing]
        if not remaining:
            return "Complete"
        return f"Needs: {', '.join(remaining)}"


@admin.register(PortfolioVideo)
class PortfolioVideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "profile_link",
        "video_source",
        "has_uploaded_file",
        "content_type",
        "category",
        "views",
        "created_at",
    )
    list_filter = (
        "video_source",
        "content_type",
        "category",
        UploadAvailabilityListFilter,
    )
    search_fields = (
        "title",
        "profile__user__username",
        "profile__cname",
        "url",
        "uploaded_file",
    )
    search_help_text = "Search by title, username, company name, source URL, or uploaded file path."
    autocomplete_fields = ("profile",)
    list_select_related = ("profile", "profile__user")
    readonly_fields = (
        "playback_link",
        "media_preview",
        "uploaded_file_name",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    actions = ("reset_view_counts",)
    list_per_page = 25

    fieldsets = (
        (
            "Video",
            {
                "fields": (
                    "profile",
                    "title",
                    "video_source",
                    "url",
                    "uploaded_file",
                    "uploaded_file_name",
                    "playback_link",
                    "media_preview",
                )
            },
        ),
        (
            "Presentation",
            {
                "fields": (
                    "thumbnail_url",
                    "content_type",
                    "category",
                    "duration",
                )
            },
        ),
        (
            "Performance",
            {
                "fields": (
                    "views",
                    "sort_order",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.action(description="Reset selected video view counts to zero")
    def reset_view_counts(self, request, queryset):
        updated = queryset.update(views=0)
        self.message_user(request, f"Reset views for {updated} video(s).")

    @admin.display(description="Profile", ordering="profile__user__username")
    def profile_link(self, obj):
        url = reverse("admin:portfolio_editorprofile_change", args=[obj.profile_id])
        return format_html('<a href="{}">@{}</a>', url, obj.profile.user.username)

    @admin.display(boolean=True, description="Upload")
    def has_uploaded_file(self, obj):
        return obj.has_uploaded_file

    @admin.display(description="Stored file")
    def uploaded_file_name(self, obj):
        return obj.uploaded_file.name or "No uploaded file"

    @admin.display(description="Playback")
    def playback_link(self, obj):
        playback_url = admin_video_destination(obj)
        if not playback_url:
            return "No playback source available."
        return format_html('<a href="{}" target="_blank" rel="noreferrer">Open playback page</a>', playback_url)

    @admin.display(description="Preview")
    def media_preview(self, obj):
        if obj.has_uploaded_file:
            playback_url = admin_video_destination(obj)
            return format_html(
                '<video controls preload="metadata" style="max-width:320px;border-radius:12px;background:#000;">'
                '<source src="{}" type="video/mp4"></video>',
                playback_url,
            )
        if obj.url:
            return format_html('<a href="{}" target="_blank" rel="noreferrer">{}</a>', obj.url, obj.url)
        return "No preview available."


@admin.register(SkillTag)
class SkillTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "updated_at")
    search_fields = ("name", "slug")
    ordering = ("sort_order", "name")


@admin.register(EditorSkill)
class EditorSkillAdmin(admin.ModelAdmin):
    list_display = ("profile", "skill", "created_at")
    list_select_related = ("profile", "profile__user", "skill")
    search_fields = ("profile__user__username", "profile__cname", "skill__name")
    autocomplete_fields = ("profile", "skill")
    date_hierarchy = "created_at"


@admin.register(VideoDownloadRequest)
class VideoDownloadRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "video",
        "requester",
        "status",
        "has_active_grant",
        "requested_at",
        "reviewed_at",
    )
    list_filter = ("status", "requested_at", "reviewed_at")
    list_select_related = ("video", "video__profile", "video__profile__user", "requester", "reviewed_by")
    search_fields = (
        "video__title",
        "requester__username",
        "video__profile__user__username",
        "video_title_snapshot",
    )
    autocomplete_fields = ("video", "requester", "reviewed_by")
    readonly_fields = ("requested_at", "reviewed_at", "approved_at")
    date_hierarchy = "requested_at"

    @admin.display(boolean=True, description="Grant")
    def has_active_grant(self, obj):
        try:
            grant = obj.download_grant
        except ObjectDoesNotExist:
            grant = None
        return bool(grant and grant.is_active and grant.revoked_at is None)


@admin.register(VideoDownloadGrant)
class VideoDownloadGrantAdmin(admin.ModelAdmin):
    list_display = ("user", "video", "granted_by", "is_active", "created_at", "revoked_at")
    list_filter = ("is_active", "created_at", "revoked_at")
    list_select_related = ("user", "video", "video__profile", "video__profile__user", "granted_by")
    search_fields = ("user__username", "video__title", "video__profile__user__username")
    autocomplete_fields = ("user", "video", "granted_by", "source_request")
    date_hierarchy = "created_at"


@admin.register(FollowRelationship)
class FollowRelationshipAdmin(admin.ModelAdmin):
    list_display = ("follower", "followed", "created_at")
    list_select_related = ("follower", "follower__user", "followed", "followed__user")
    search_fields = ("follower__user__username", "followed__user__username")
    autocomplete_fields = ("follower", "followed")
    date_hierarchy = "created_at"


@admin.register(VideoReaction)
class VideoReactionAdmin(admin.ModelAdmin):
    list_display = ("profile", "video", "reaction_type", "created_at")
    list_filter = ("reaction_type",)
    list_select_related = ("profile", "profile__user", "video", "video__profile", "video__profile__user")
    search_fields = (
        "profile__user__username",
        "video__title",
        "video__profile__user__username",
    )
    autocomplete_fields = ("profile", "video")
    date_hierarchy = "created_at"


@admin.register(VideoStarRating)
class VideoStarRatingAdmin(admin.ModelAdmin):
    list_display = ("profile", "video", "rating", "updated_at")
    list_filter = ("rating",)
    list_select_related = ("profile", "profile__user", "video", "video__profile", "video__profile__user")
    search_fields = (
        "profile__user__username",
        "video__title",
        "video__profile__user__username",
    )
    autocomplete_fields = ("profile", "video")
    date_hierarchy = "updated_at"
