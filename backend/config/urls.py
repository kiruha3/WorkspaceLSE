from django.urls import path
from apps.accounts.views import csrf_view, login_view, logout_view, MeView

urlpatterns = [
    path("api/v1/auth/csrf/",csrf_view),
    path("api/v1/auth/login/",login_view),
    path("api/v1/auth/logout/",logout_view),
    path("api/v1/me/",MeView.as_view()),
]
