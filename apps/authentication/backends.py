from django.contrib.auth.models import Group
from rest_framework_simplejwt.tokens import AccessToken
from django_auth_ldap.backend import LDAPBackend
from .models import DepartmentRole


class LDAPJWTBackend(LDAPBackend):
    def authenticate(self, request, username, password, **kwargs):
        print(f"\nAttempting LDAP authentication for: {username}")
        user = super().authenticate(request, username, password, **kwargs)

        if user:
            print(f"Authentication SUCCESS for: {username}")
            self.populate_user(user)   # Синхронизация данных из LDAP
            self.assign_roles(user)    # Назначение ролей на основе групп из LDAP
            token = AccessToken.for_user(user)   # Генерация токена JWT
            user.token = str(token)   # Сохранение токена во временном атрибуте
        print(f"Authentication FAILED for: {username}")
        return user

    def assign_roles(self, user):
        user.groups.clear()                 # Очистка всех групп пользователя
        has_special_permissions = False     # Флаг, определяющий наличие спецправ

        if hasattr(user, 'ldap_user') and hasattr(user.ldap_user, 'group_dns'):   # Проверка наличия LDAP-атрибутов
            for group_dn in user.ldap_user.group_dns:   # Перебор всех групп пользователя в LDAP
                if 'CPortal_' in group_dn:
                    try:
                        role = DepartmentRole.objects.get(ldap_group_dn=group_dn)   # Поиск соответствия в БД
                        group, _ = Group.objects.get_or_create(name=role.name)      # Получаем/создаем группу
                        user.groups.add(group)                                      # Назначение пользователю группы
                        has_special_permissions = True                              # Меняем флаг
                    except DepartmentRole.DoesNotExist:
                        pass                                                        # Если спецгруппы нет, пропускаем

        if not has_special_permissions:                                             # Если спецгруппы не найдены, даем
            viewer_group = Group.objects.get_or_create(name='Viewer')               # даем права обычного пользователя
            user.groups.add(viewer_group)
