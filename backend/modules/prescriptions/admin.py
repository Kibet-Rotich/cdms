from django.contrib import admin

from .models import Prescription


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("code", "prescriber_name", "issued_at", "quantity", "quantity_dispensed", "status")
    list_filter = ("status",)
    search_fields = ("code", "prescriber_name", "prescriber_licence")
