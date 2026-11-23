from django.urls import path

from . import views

urlpatterns = [
    path("dispenses/preview", views.DispensePreviewView.as_view()),
    path("dispenses", views.DispenseCreateView.as_view()),
    path("dispenses/<uuid:dispense_id>", views.DispenseDetailView.as_view()),
    path("dispenses/<uuid:dispense_id>/void", views.DispenseVoidView.as_view()),
    path("facilities/<uuid:facility_id>/dispenses", views.FacilityDispensesView.as_view()),
]
