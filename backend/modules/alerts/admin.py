from django.contrib import admin

from .models import Alert, Evaluation, RuleConfig


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "rule_code", "severity", "action", "ack_reason", "referral_made")
    list_filter = ("rule_code", "severity", "action")


@admin.register(RuleConfig)
class RuleConfigAdmin(admin.ModelAdmin):
    list_display = ("code", "enabled", "params")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "patient_id")
