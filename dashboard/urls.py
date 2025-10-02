from django.urls import path
from .views import (
    home,
    RoleAwareLoginView, role_router,
    master_dashboard, client_dashboard,
    api_license_keys_summary,
    api_client_metrics,
    api_master_recent_activities
)
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path("", home, name="home"),   # <-- add home at root
    path("login/",  RoleAwareLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"),
         name="logout"),  # <— change here


    # after login, send them here to jump to correct dashboard (used by our LoginView)
    path("route/", role_router, name="role_router"),

    # dashboards
    path("dash/master/", master_dashboard, name="master_dashboard"),
    path("dash/<slug:org_slug>/", client_dashboard, name="client_dashboard"),

    # ---- API (master only) ----
    path("api/admin/license-keys/summary",
         api_license_keys_summary, name="api_license_keys_summary"),
    # Client metrics (org-agnostic v1: Lott.de)
    path("api/client/metrics", api_client_metrics, name="api_client_metrics"),
    path("api/master/recent-activities", api_master_recent_activities,
         name="api_master_recent_activities"),
]
