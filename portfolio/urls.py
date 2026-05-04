from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path

from . import views
from .sitemaps import ProfileSitemap, StaticViewSitemap

app_name = "portfolio"
sitemaps = {
    "static": StaticViewSitemap,
    "profiles": ProfileSitemap,
}

urlpatterns = [
    path("", views.frontend_shell, name="home"),
    path("admin/", views.frontend_shell, name="admin-dashboard"),
    path("discover/", views.frontend_shell, name="discover"),
    path("dashboard/", views.frontend_shell, name="dashboard"),
    path("about/", views.about_view, name="about"),
    path("api/secure/", include("portfolio.api_secure.urls")),
    path("robots.txt", views.robots_txt_view, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("api/profiles/<str:username>/avatar/", views.profile_avatar_view, name="profile-avatar"),
    path("auth/signup/", views.signup_view, name="signup"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("api/bootstrap/", views.bootstrap_view, name="bootstrap"),
    path("api/search/", views.search_view, name="search"),
    path("api/profile/", views.profile_update_view, name="profile-update"),
    path("api/contacts/", views.contact_update_view, name="contact-update"),
    path("api/follow/<str:username>/toggle/", views.follow_toggle_view, name="follow-toggle"),
    path("api/videos/create/", views.video_create_view, name="video-create"),
    path("api/videos/<uuid:video_id>/update/", views.video_update_view, name="video-update"),
    path("api/videos/<uuid:video_id>/delete/", views.video_delete_view, name="video-delete"),
    path("api/videos/<uuid:video_id>/move/", views.video_move_view, name="video-move"),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/play/",
        views.video_play_view,
        name="video-play",
    ),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/like/",
        views.video_like_toggle_view,
        name="video-like",
    ),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/react/",
        views.video_like_toggle_view,
        name="video-react",
    ),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/rate/",
        views.video_rating_update_view,
        name="video-rate",
    ),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/stream/",
        views.video_stream_view,
        name="video-stream",
    ),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/download/",
        views.video_download_view,
        name="video-download",
    ),
    path("api/telegram/webhook/<str:secret>/", views.telegram_webhook_view, name="telegram-webhook"),
    path("<str:username>/", views.frontend_shell, name="public-profile"),
    re_path(
        r"^(?P<requested_path>(?!media/|static/).*)$",
        views.friendly_not_found_view,
        name="friendly-404",
    ),
]
