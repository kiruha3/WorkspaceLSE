import uuid
from django.db import models


class Reference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True
        ordering = ["code", "id"]

    def __str__(self):
        return self.name


class Department(Reference):
    pass


class Position(Reference):
    pass


class Specialty(Reference):
    pass
