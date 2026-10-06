from rest_framework.permissions import BasePermission


class IsHouseholdAdmin(BasePermission):
    """Django's staff flag doubles as the household admin role."""
    message = 'Only a household admin can do this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
