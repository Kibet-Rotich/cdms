from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "role", "licence_number", "status")
    list_filter = ("role", "status")
    search_fields = ("full_name", "email", "licence_number")
    exclude = ("password",)
