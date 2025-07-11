from django_auth_ldap.backend import LDAPBackend
from rest_framework_simplejwt.tokens import AccessToken


class LDAPJWTBackend(LDAPBackend):
    def authenticate(self, request, username, password, **kwargs):
        user = super().authenticate(request, username, password, **kwargs)

        if user:
            self.populate_user(user)
            token = AccessToken.for_user(user)
            user.token = str(token)

        return user
