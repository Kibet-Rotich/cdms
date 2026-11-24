from django.urls import path

from . import views

urlpatterns = [
    path("audit-events", views.AuditEventListView.as_view()),
    path("audit-events/verify", views.AuditVerifyView.as_view()),
]
