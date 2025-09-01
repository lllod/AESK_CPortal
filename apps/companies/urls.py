from django.urls import path

from apps.companies.views import ExcelUploadView

urlpatterns = [
    path('upload/', ExcelUploadView.as_view(), name='companies-excel-upload'),
]