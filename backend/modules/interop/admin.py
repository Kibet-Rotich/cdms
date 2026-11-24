from django.contrib import admin

from .models import MockRegistryRecord


@admin.register(MockRegistryRecord)
class MockRegistryRecordAdmin(admin.ModelAdmin):
    list_display = ("kind", "key")
    list_filter = ("kind",)
    search_fields = ("key",)
