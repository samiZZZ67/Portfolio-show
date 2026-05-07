from importlib.util import find_spec

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
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
