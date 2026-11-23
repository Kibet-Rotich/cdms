from django.urls import path

from . import views

urlpatterns = [
    path("prescriptions/preview", views.PrescriptionPreviewView.as_view()),
    path("prescriptions", views.PrescriptionCreateView.as_view()),
    path("prescriptions/by-code/<str:code>", views.PrescriptionDetailView.as_view()),
    path("prescriptions/<uuid:prescription_id>", views.PrescriptionDetailView.as_view()),
    path("prescriptions/<uuid:prescription_id>/cancel", views.PrescriptionCancelView.as_view()),
    path("patients/<uuid:patient_id>/prescriptions", views.PatientPrescriptionsView.as_view()),
]
