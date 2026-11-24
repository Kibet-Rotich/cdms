from django.urls import path

from . import views

urlpatterns = [
    path("alerts", views.AlertListView.as_view()),
    path("alerts/<uuid:alert_id>", views.AlertDetailView.as_view()),
    path("alerts/<uuid:alert_id>/referral", views.AlertReferralView.as_view()),
    path("alert-rules", views.AlertRuleListView.as_view()),
    path("alert-rules/<str:code>", views.AlertRuleUpdateView.as_view()),
]
