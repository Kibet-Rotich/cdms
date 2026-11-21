from django.contrib import admin

from .models import OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "processed_at")
    list_filter = ("name",)
    readonly_fields = [f.name for f in OutboxEvent._meta.fields]
