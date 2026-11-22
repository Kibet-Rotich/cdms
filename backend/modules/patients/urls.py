from django.urls import path

from . import views

urlpatterns = [
    path("patients/search", views.PatientSearchView.as_view()),
    path("patients", views.PatientCreateView.as_view()),
    path("patients/<uuid:patient_id>", views.PatientDetailView.as_view()),
    path("patients/<uuid:patient_id>/possible-duplicates", views.PatientDuplicatesView.as_view()),
]
