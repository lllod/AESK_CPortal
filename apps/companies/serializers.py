from rest_framework import serializers
from django.core.validators import FileExtensionValidator

from apps.companies.models import UploadLog


class ExcelUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])],
        help_text="Excel-файл с данными контрагентов (XLSX/XLS)"
    )

    class Meta:
        model = UploadLog
        fields = ('file',)

    def validate_file(self, value):
        """Ограничение размера файла (для безопасности)"""
        max_size = 30 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("Максимальный размер файла - 30 Мб")
        return value
