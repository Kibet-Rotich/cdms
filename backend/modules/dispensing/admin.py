from django.contrib import admin

from .models import Dispense


@admin.register(Dispense)
class DispenseAdmin(admin.ModelAdmin):
    list_display = ("dispensed_at", "pharmacist_name", "quantity", "is_paper", "status")
    list_filter = ("status", "is_paper")
