from django.db import models

from core.models import BaseModel, CountyScoped


class DrugClass(models.Model):
    """Alert rules work at class level (e.g. OPIOID, BENZODIAZEPINE)."""

    code = models.CharField(max_length=30, primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "drug classes"

    def __str__(self):
        return self.name


class Drug(BaseModel):
    class Unit(models.TextChoices):
        TABLET = "TABLET", "Tablet"
        CAPSULE = "CAPSULE", "Capsule"
        ML = "ML", "mL"
        AMPOULE = "AMPOULE", "Ampoule/vial"
        PATCH = "PATCH", "Patch"

    name = models.CharField(max_length=150)  # display name incl. strength, e.g. "Tramadol 50 mg capsule"
    generic_name = models.CharField(max_length=100)
    drug_class = models.ForeignKey(DrugClass, on_delete=models.PROTECT, related_name="drugs")
    strength_mg = models.DecimalField(max_digits=10, decimal_places=3, help_text="Strength per unit (mg, or mcg/h for patches)")
    unit = models.CharField(max_length=10, choices=Unit.choices)
    form = models.CharField(max_length=50, blank=True, default="")
    # Daily MME = quantity x strength_mg x mme_factor / days_supply. Only for opioids.
    mme_factor = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    monitored = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["generic_name", "strength_mg"]

    def __str__(self):
        return self.name


class Facility(BaseModel, CountyScoped):
    class Type(models.TextChoices):
        HOSPITAL = "HOSPITAL", "Hospital"
        HEALTH_CENTRE = "HEALTH_CENTRE", "Health centre"
        CLINIC = "CLINIC", "Clinic"
        RETAIL_PHARMACY = "RETAIL_PHARMACY", "Retail pharmacy"

    class Ownership(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        PRIVATE = "PRIVATE", "Private"
        FAITH_BASED = "FAITH_BASED", "Faith-based"

    kmhfl_code = models.CharField(max_length=20, unique=True, help_text="Kenya Master Health Facility List code")
    name = models.CharField(max_length=150)
    facility_type = models.CharField(max_length=20, choices=Type.choices)
    ownership = models.CharField(max_length=20, choices=Ownership.choices, default=Ownership.PRIVATE)
    sub_county = models.CharField(max_length=60)
    ppb_licence_number = models.CharField(max_length=30, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "facilities"

    def __str__(self):
        return self.name


class Practitioner(BaseModel):
    """Local copy of practitioners verified against the national registers (via the Interop module)."""

    licence_number = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=150)
    cadre = models.CharField(max_length=40)  # MEDICAL_OFFICER, CLINICAL_OFFICER, PHARMACIST, PHARM_TECH
    regulator = models.CharField(max_length=20)  # KMPDC, COC, PPB
    status = models.CharField(max_length=20, default="ACTIVE")
    verified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.licence_number})"
