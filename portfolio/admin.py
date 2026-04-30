from django.contrib import admin

from .models import EditorProfile, PortfolioVideo


class PortfolioVideoInline(admin.TabularInline):
    model = PortfolioVideo
    extra = 0
    fields = ("title", "video_source", "content_type", "category", "duration", "views", "sort_order")


@admin.register(EditorProfile)
class EditorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "has_contact_method", "updated_at")
    search_fields = ("user__username", "user__email", "telegram", "whatsapp", "phone")
    inlines = [PortfolioVideoInline]


@admin.register(PortfolioVideo)
class PortfolioVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "video_source", "content_type", "category", "views", "sort_order")
    list_filter = ("video_source", "content_type", "category")
    search_fields = ("title", "profile__user__username", "url")
