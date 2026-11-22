from django.contrib import admin

from .models import Drug, DrugClass, Facility, Practitioner


@admin.register(DrugClass)
class DrugClassAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = ("name", "generic_name", "drug_class", "strength_mg", "unit", "mme_factor", "monitored")
    list_filter = ("drug_class", "monitored")


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "kmhfl_code", "facility_type", "sub_county", "county_code")
    list_filter = ("facility_type", "sub_county")


@admin.register(Practitioner)
class PractitionerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "licence_number", "cadre", "regulator", "status")
