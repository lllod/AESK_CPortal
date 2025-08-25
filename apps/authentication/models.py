from django.db import models


# class Department(models.Model):
#     name = models.CharField(max_length=255)
#     ldap_dn = models.CharField(max_length=255, unique=True)
#
#     def __str__(self):
#         return self.name


class DepartmentRole(models.Model):
    # department = models.ForeignKey(Department, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, unique=True)
    ldap_group_dn = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
