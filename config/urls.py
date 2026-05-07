from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("portfolio.urls")),
    path('api/auth/', include('dj_rest_auth.urls')),  # Login, logout, password reset
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),  # Registration
    path('accounts/', include('allauth.urls')), 
]
