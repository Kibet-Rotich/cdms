from django.contrib import admin

from .models import MedicationEvent


@admin.register(MedicationEvent)
class MedicationEventAdmin(admin.ModelAdmin):
    list_display = ("kind", "drug_name", "patient_id", "start_date", "facility_name", "prescriber_name", "status")
    list_filter = ("kind", "class_code", "status")
