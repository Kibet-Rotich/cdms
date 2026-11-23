from django.contrib import admin

from .models import StockReceipt


@admin.register(StockReceipt)
class StockReceiptAdmin(admin.ModelAdmin):
    list_display = ("received_at", "facility_id", "drug_id", "quantity", "source")
