from django.urls import path
from .views import LDAPLoginView, LDAPLogoutView

urlpatterns = [
    path('login/', LDAPLoginView.as_view(), name='login'),
    path('logout/', LDAPLogoutView.as_view(), name='logout'),
]
