from django.db import models

from core.models import BaseModel, CountyScoped


class Patient(BaseModel, CountyScoped):
    class Sex(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        OTHER = "O", "Other / unknown"

    # DHA Client Registry ID. Empty for patients registered locally and not yet verified.
    cr_id = models.CharField(max_length=40, blank=True, default="", db_index=True)
    first_name = models.CharField(max_length=60)
    middle_name = models.CharField(max_length=60, blank=True, default="")
    last_name = models.CharField(max_length=60)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices)
    phone = models.CharField(max_length=20, blank=True, default="")
    verified = models.BooleanField(default=False, help_text="True when matched in the Client Registry")
    registered_by = models.UUIDField(null=True, blank=True)
    registered_at_facility = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return " ".join(p for p in [self.first_name, self.middle_name, self.last_name] if p)

    def __str__(self):
        return self.full_name


class PatientIdentifier(models.Model):
    class IdType(models.TextChoices):
        NATIONAL_ID = "NATIONAL_ID", "National ID"
        MAISHA_NAMBA = "MAISHA_NAMBA", "Maisha Namba"
        BIRTH_CERT = "BIRTH_CERT", "Birth certificate"
        PASSPORT = "PASSPORT", "Passport"
        REFUGEE_ID = "REFUGEE_ID", "Refugee ID"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="identifiers")
    id_type = models.CharField(max_length=20, choices=IdType.choices)
    value = models.CharField(max_length=40)

    class Meta:
        unique_together = [("id_type", "value")]

    def __str__(self):
        return f"{self.id_type}:{self.value}"
