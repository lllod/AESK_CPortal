from rest_framework.permissions import BasePermission


class HasServiceAcces(BasePermission):
    def has_permission(self, request, view):
        required_service = getattr(view, 'requiered_service', None)
        return request.user.groups.filter(name=required_service).exists()


class IsSuperUserOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_superuser

