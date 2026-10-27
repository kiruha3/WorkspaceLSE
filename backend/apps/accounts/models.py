import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]


class RolePermission(models.Model):
    role = models.ForeignKey(Role, related_name="permissions", on_delete=models.CASCADE)
    permission_code = models.CharField(max_length=100)
    scope = models.CharField(max_length=20, choices=[(v,v) for v in ("own", "departments", "institution")])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "permission_code"], name="unique_role_action")]
