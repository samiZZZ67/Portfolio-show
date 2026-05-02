from rest_framework.permissions import BasePermission


class IsAuthenticatedEditor(BasePermission):
    message = "Only authenticated editor accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and hasattr(request.user, "editor_profile")
            and request.user.editor_profile.is_editor
        )


class IsAuthenticatedUser(BasePermission):
    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
