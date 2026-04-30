from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.frontend_shell, name="home"),
    path("discover/", views.frontend_shell, name="discover"),
    path("dashboard/", views.frontend_shell, name="dashboard"),
    path("auth/signup/", views.signup_view, name="signup"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("api/bootstrap/", views.bootstrap_view, name="bootstrap"),
    path("api/search/", views.search_view, name="search"),
    path("api/profile/", views.profile_update_view, name="profile-update"),
    path("api/contacts/", views.contact_update_view, name="contact-update"),
    path("api/videos/create/", views.video_create_view, name="video-create"),
    path("api/videos/<uuid:video_id>/update/", views.video_update_view, name="video-update"),
    path("api/videos/<uuid:video_id>/delete/", views.video_delete_view, name="video-delete"),
    path("api/videos/<uuid:video_id>/move/", views.video_move_view, name="video-move"),
    path(
        "api/profiles/<str:username>/videos/<uuid:video_id>/play/",
        views.video_play_view,
        name="video-play",
    ),
    path("<str:username>/", views.frontend_shell, name="public-profile"),
]
