from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("drug-classes", views.DrugClassViewSet, basename="drug-class")
router.register("drugs", views.DrugViewSet, basename="drug")
router.register("facilities", views.FacilityViewSet, basename="facility")

urlpatterns = [
    path("practitioners/verify", views.VerifyPractitionerView.as_view()),
    *router.urls,
]
