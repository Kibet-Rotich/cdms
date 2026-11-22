import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import pilot_county
from core.permissions import Roles


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", Roles.SYSTEM_ADMIN)
        extra.setdefault("status", User.Status.ACTIVE)
        extra.setdefault("full_name", "System Administrator")
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, default="")
    role = models.CharField(max_length=20, choices=Roles.CHOICES)
    # Professional licence (KMPDC / Clinical Officers Council / PPB). Used as the prescriber key.
    licence_number = models.CharField(max_length=30, blank=True, default="", db_index=True)
    cadre = models.CharField(max_length=40, blank=True, default="")
    # Reference to registry.Facility by ID only (no cross-module foreign key).
    facility_id = models.UUIDField(null=True, blank=True, db_index=True)
    county_code = models.CharField(max_length=3, default=pilot_county)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    is_staff = models.BooleanField(default=False)
    approved_by = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    @property
    def is_active(self):
        # Only approved, non-suspended accounts can authenticate.
        return self.status == self.Status.ACTIVE

    def __str__(self):
        return f"{self.full_name} <{self.email}>"
