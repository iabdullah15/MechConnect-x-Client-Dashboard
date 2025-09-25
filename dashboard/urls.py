from django.urls import path
from .views import (
    home,
    RoleAwareLoginView, role_router,
    master_dashboard, client_dashboard,
)
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path("", home, name="home"),   # <-- add home at root
    path("login/",  RoleAwareLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),  # <— change here


    # after login, send them here to jump to correct dashboard (used by our LoginView)
    path("route/", role_router, name="role_router"),

    # dashboards
    path("dash/master/", master_dashboard, name="master_dashboard"),
    path("dash/<slug:org_slug>/", client_dashboard, name="client_dashboard"),
]
