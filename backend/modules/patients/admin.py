from django.contrib import admin

from .models import Patient, PatientIdentifier


class IdentifierInline(admin.TabularInline):
    model = PatientIdentifier
    extra = 0


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "date_of_birth", "sex", "verified", "cr_id")
    search_fields = ("first_name", "last_name", "cr_id", "identifiers__value")
    inlines = [IdentifierInline]
