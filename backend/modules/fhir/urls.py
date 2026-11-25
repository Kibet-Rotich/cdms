from django.urls import path

from . import views

urlpatterns = [
    path("Patient/<uuid:patient_id>", views.PatientResource.as_view()),
    path("MedicationDispense", views.MedicationDispenseSearch.as_view()),
    path("MedicationRequest", views.MedicationRequestSearch.as_view()),
]
