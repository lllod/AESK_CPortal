from django.db import models
import uuid

from apps.common.managers import GetOrNoneManager


class BaseModel(models.Model):
    """
    Базовая абстрактная модель.

    Атрибуты:
        id (UUIDField): уникальный идентификатор экземпляра модели.
        created_at (DateTimeField): Дата и время создания экземпляра модели.
        updated_at (DateTimeField): Дата и время обновления экземпляра модели.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = GetOrNoneManager()

    class Meta:
        abstract = True
