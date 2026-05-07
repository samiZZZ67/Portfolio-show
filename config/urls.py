from importlib.util import find_spec

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.ico", permanent=True)),
    path("favicon.png", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.png", permanent=True)),
    path("apple-touch-icon.png", RedirectView.as_view(url=f"{settings.STATIC_URL}apple-touch-icon.png", permanent=True)),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
]

if find_spec("dj_rest_auth"):
    urlpatterns.extend(
        [
            path('api/auth/', include('dj_rest_auth.urls')),
            path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
        ]
    )

urlpatterns.append(path("", include("portfolio.urls")))
