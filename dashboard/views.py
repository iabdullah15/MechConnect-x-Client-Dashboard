from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Organization
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from .services import fetch_license_key_stats
from .services import (
    fetch_lott_users_last5,
    fetch_lott_verifications_last5,
    fetch_support_last5,
    fetch_chat_threads_last5,
    fetch_recent_activities,
    fetch_most_active_days,
    fetch_most_active_hours,        # <-- add
    fetch_top_car_diagnoses,        # <-- add
    fetch_related_parts_click_rate,
    fetch_parts_stats,
)

# --- NEW: Home page view ---


def home(request):
    """
    - If not authenticated: show a friendly welcome + Login button.
    - If authenticated:
        * MASTER (or superuser): show link to Master Dashboard and links to all client dashboards.
        * CLIENT: show link to their own client dashboard only.
    """
    user = request.user
    context = {"is_authenticated": user.is_authenticated,
               "is_master": False, "orgs": [], "client_org": None}

    if user.is_authenticated:
        if hasattr(user, "is_master") and user.is_master():
            context["is_master"] = True
            context["orgs"] = list(Organization.objects.all().order_by("name"))
        else:
            # may be None if not assigned
            context["client_org"] = user.organization

    return render(request, "home.html", context)


class RoleAwareLoginView(LoginView):
    template_name = "login.html"

    def get_success_url(self):
        user = self.request.user
        if not user.is_authenticated:
            return reverse("login")
        if user.is_master():
            return reverse("master_dashboard")
        if user.organization_id and getattr(user, "organization", None):
            return reverse("client_dashboard", kwargs={"org_slug": user.organization.slug})
        return reverse("role_router")

    @classmethod
    def as_logout(cls):
        return LogoutView.as_view()


@login_required
def role_router(request):
    user = request.user
    if user.is_master():
        return redirect("master_dashboard")
    if user.organization_id and getattr(user, "organization", None):
        return redirect("client_dashboard", org_slug=user.organization.slug)
    return redirect("login")


@login_required
def master_dashboard(request):
    # non-masters get redirected to their own client dashboard
    if not request.user.is_master():
        if request.user.organization_id and getattr(request.user, "organization", None):
            return redirect("client_dashboard", org_slug=request.user.organization.slug)
        return redirect("login")

    orgs = Organization.objects.all().order_by("name")
    current = request.GET.get("org") or (orgs[0].slug if orgs else None)
    org = get_object_or_404(Organization, slug=current) if current else None
    return render(request, "dashboard_master.html", {"orgs": orgs, "org": org})


@login_required
def client_dashboard(request, org_slug):
    org = get_object_or_404(Organization, slug=org_slug)
    # Masters (incl. superuser) can view any org; clients only their own org
    if not request.user.is_master():
        if not (request.user.organization and request.user.organization.slug == org_slug):
            return redirect("role_router")
    return render(request, "dashboard_client.html", {"org": org})


@login_required
def api_license_keys_summary(request):
    # Only MASTER (or superuser) can see master metrics API
    if not request.user.is_master():
        return HttpResponseForbidden("Forbidden")

    try:
        data = fetch_license_key_stats()
        return JsonResponse({"ok": True, "data": data})
    except Exception as e:
        # Keep it simple; return zeros on error
        return JsonResponse({"ok": False, "error": str(e), "data": {"new": 0, "active": 0, "inactive": 0, "total": 0}}, status=200)


@login_required
def api_client_metrics(request):
    """
    Org-agnostic v1; supports optional:
      ?licenseKey=... 
      ?period=all|am|pm
      ?dateRange=7d|1m|1y
      ?granularity=hourly|daily|weekly
    """
    license_key = request.GET.get("licenseKey") or None
    period      = request.GET.get("period", "all")
    date_range  = request.GET.get("dateRange") or None
    granularity = request.GET.get("granularity", "daily")

    try:
        users     = fetch_lott_users_last5()
        verifs    = fetch_lott_verifications_last5(license_key=license_key)
        support   = fetch_support_last5(license_key=license_key)
        threads   = fetch_chat_threads_last5(license_key=license_key)
        recents   = fetch_recent_activities(license_key=license_key)
        weekdays  = fetch_most_active_days(period=period, license_key=license_key)
        hours     = fetch_most_active_hours(period=period, license_key=license_key)
        topcars   = fetch_top_car_diagnoses(license_key=license_key, date_range=date_range)
        rp_click  = fetch_related_parts_click_rate(granularity, license_key)
        parts     = fetch_parts_stats(license_key)

        return JsonResponse({
            "ok": True,
            "data": {
                "user_chart": users,
                "verify_chart": verifs,
                "support_chart": support,
                "chat_thread_chart": threads,
                "recent_activities": recents,
                "most_active_days": weekdays,
                "most_active_hours": hours,
                "top_car_diagnoses": topcars,
                "related_parts_click_rate": rp_click,
                "parts_stats": parts,
            }
        })
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "data": {
                "user_chart": [],
                "verify_chart": [],
                "support_chart": [],
                "chat_thread_chart": [],
                "recent_activities": [],
                "most_active_days": [],
                "most_active_hours": {
                    "period": "all",
                    "totalDistinctUsers": 0,
                    "perHour": [{"hour": h, "distinctUsers": 0} for h in range(24)]
                },
                "top_car_diagnoses": {"top5Makes": [], "top5Models": []},
                "related_parts_click_rate": [],
                "parts_stats": [],
            }
        }, status=200)