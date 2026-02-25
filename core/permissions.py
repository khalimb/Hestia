from rest_framework.permissions import BasePermission


class IsCustomItemOwner(BasePermission):
    """Only the creator of a custom item (subject, expense type) can modify/delete it."""

    def has_object_permission(self, request, view, obj):
        if obj.is_default:
            return False
        return obj.created_by == request.user
