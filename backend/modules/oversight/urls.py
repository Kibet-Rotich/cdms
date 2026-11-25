from django.urls import path

from . import views

urlpatterns = [
    path("oversight/summary", views.SummaryView.as_view()),
    path("oversight/trends", views.TrendsView.as_view()),
    path("oversight/outliers/prescribers", views.PrescriberOutliersView.as_view()),
    path("oversight/outliers/pharmacies", views.PharmacyOutliersView.as_view()),
    path("oversight/hotspots", views.HotspotsView.as_view()),
    path("oversight/flagged-patients", views.FlaggedPatientsView.as_view()),
    path("oversight/flagged-patients/<str:ref>/reveal", views.RevealFlaggedPatientView.as_view()),
    path("oversight/supply-reconciliation", views.SupplyReconciliationView.as_view()),
    path("oversight/reports/export", views.ExportView.as_view()),
]
