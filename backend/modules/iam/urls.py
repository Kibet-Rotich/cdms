from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/refresh", TokenRefreshView.as_view()),
    path("me", views.MeView.as_view()),
    path("users/register", views.RegisterView.as_view()),
    path("users", views.UserListView.as_view()),
    path("users/<uuid:user_id>/approve", views.ApproveUserView.as_view()),
    path("users/<uuid:user_id>/suspend", views.SuspendUserView.as_view()),
]
