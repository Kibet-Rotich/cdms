from django.urls import path

from . import views

urlpatterns = [
    path("patients/<uuid:patient_id>/medication-history", views.MedicationHistoryView.as_view()),
    path("patients/<uuid:patient_id>/medication-summary", views.MedicationSummaryView.as_view()),
]
