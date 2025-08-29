from django.utils import timezone


def upload_log_file_name_of_nine() -> str:
    """Генерация дефолтного имени Excel-файла"""
    return f'of-9-file-{timezone.now():%Y%m%d%H%M%S}.xlsx'
