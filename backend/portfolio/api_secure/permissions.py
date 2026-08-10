from rest_framework.permissions import BasePermission

from portfolio.models import AccountRole


def has_admin_role(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    profile = getattr(user, "editor_profile", None)
    return bool(profile and profile.role == AccountRole.ADMIN)


class IsAuthenticatedEditor(BasePermission):
    message = "Only authenticated editor accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and hasattr(request.user, "editor_profile")
            and request.user.editor_profile.is_editor
        )


class IsAuthenticatedAdmin(BasePermission):
    message = "Only authenticated admin accounts can perform this action."

    def has_permission(self, request, view):
        return has_admin_role(request.user)


class IsAuthenticatedEditorOrAdmin(BasePermission):
    message = "Only authenticated editor or admin accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (
                has_admin_role(request.user)
                or (
                    hasattr(request.user, "editor_profile")
                    and request.user.editor_profile.is_editor
                )
            )
        )


class IsAuthenticatedUser(BasePermission):
    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
