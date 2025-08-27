from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import Group


class CustomAccessToken(AccessToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)

        groups = user.groups.all().values_list('name', flat=True)
        token['groups'] = list(groups)

        if hasattr(user, 'ldap_user') and 'department' in user.ldap_user.attrs:
            token['department'] = user.ldap_user.attrs['department'][0]

        return token
