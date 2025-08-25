from django.utils.deprecation import MiddlewareMixin
from .backends import LDAPJWTBackend


class LDAPUserRefreshMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            backend = LDAPJWTBackend()
            backend.populate_user(username=request.user.username)
