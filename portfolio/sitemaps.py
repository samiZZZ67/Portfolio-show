from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import EditorProfile


class StaticViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return ["portfolio:home", "portfolio:discover"]

    def location(self, item):
        return reverse(item)


class ProfileSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return [profile for profile in EditorProfile.objects.select_related("user").all() if profile.has_contact_method()]

    def location(self, item):
        return f"/{item.user.username}/"

    def lastmod(self, item):
        return item.updated_at
