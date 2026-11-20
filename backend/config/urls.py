from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(_request):
    return JsonResponse({"status": "ok"})


api_v1 = [
    path("", include("modules.iam.urls")),
    path("", include("modules.registry.urls")),
    path("", include("modules.patients.urls")),
    path("", include("modules.history.urls")),
    path("", include("modules.prescriptions.urls")),
    path("", include("modules.dispensing.urls")),
    path("", include("modules.supply.urls")),
    path("", include("modules.alerts.urls")),
    path("", include("modules.oversight.urls")),
    path("", include("modules.audit.urls")),
]

urlpatterns = [
    path("health", health),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("fhir/", include("modules.fhir.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
