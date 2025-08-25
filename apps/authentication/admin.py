from django.contrib import admin
from django.contrib.auth.models import Group
from .models import DepartmentRole


@admin.register(DepartmentRole)
class DepartmentRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'ldap_group_dn')
    search_fields = ('name', 'ldap_group_dn')


# def create_initial_groups():
#     Group.objects.get_or_create(name='Viewer')
#     Group.objects.get_or_create(name='Staff')
#     Group.objects.get_or_create(name='Superuser')
#
# create_initial_groups()