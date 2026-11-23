from django.urls import path

from . import views

urlpatterns = [
    path("stock-receipts", views.StockReceiptCreateView.as_view()),
    path("facilities/<uuid:facility_id>/stock-receipts", views.FacilityStockReceiptsView.as_view()),
]
