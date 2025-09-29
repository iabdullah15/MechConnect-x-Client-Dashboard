from django.core.cache import cache
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
    fetch_avg_steps_per_diagnosis,
    fetch_avg_diagnosis_time,
    fetch_diy_trend,
    fetch_top_problem_reasons
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


# @login_required
# def api_client_metrics(request):
#     """
#     Org-agnostic v1; supports optional:
#       ?licenseKey=...
#       ?period=all|am|pm
#       ?dateRange=7d|1m|1y
#       ?granularity=hourly|daily|weekly
#     """
#     license_key = request.GET.get("licenseKey") or None
#     period      = request.GET.get("period", "all")
#     date_range  = request.GET.get("dateRange") or None
#     granularity = request.GET.get("granularity", "daily")

#     try:
#         users     = fetch_lott_users_last5()
#         verifs    = fetch_lott_verifications_last5(license_key=license_key)
#         support   = fetch_support_last5(license_key=license_key)
#         threads   = fetch_chat_threads_last5(license_key=license_key)
#         recents   = fetch_recent_activities(license_key=license_key)
#         weekdays  = fetch_most_active_days(period=period, license_key=license_key)
#         hours     = fetch_most_active_hours(period=period, license_key=license_key)
#         topcars   = fetch_top_car_diagnoses(license_key=license_key, date_range=date_range)
#         rp_click  = fetch_related_parts_click_rate(granularity, license_key)
#         parts     = fetch_parts_stats(license_key)

#         return JsonResponse({
#             "ok": True,
#             "data": {
#                 "user_chart": users,
#                 "verify_chart": verifs,
#                 "support_chart": support,
#                 "chat_thread_chart": threads,
#                 "recent_activities": recents,
#                 "most_active_days": weekdays,
#                 "most_active_hours": hours,
#                 "top_car_diagnoses": topcars,
#                 "related_parts_click_rate": rp_click,
#                 "parts_stats": parts,
#             }
#         })
#     except Exception as e:
#         return JsonResponse({
#             "ok": False,
#             "error": str(e),
#             "data": {
#                 "user_chart": [],
#                 "verify_chart": [],
#                 "support_chart": [],
#                 "chat_thread_chart": [],
#                 "recent_activities": [],
#                 "most_active_days": [],
#                 "most_active_hours": {
#                     "period": "all",
#                     "totalDistinctUsers": 0,
#                     "perHour": [{"hour": h, "distinctUsers": 0} for h in range(24)]
#                 },
#                 "top_car_diagnoses": {"top5Makes": [], "top5Models": []},
#                 "related_parts_click_rate": [],
#                 "parts_stats": [],
#             }
#         }, status=200)


def _cache_get(name, default):
    return cache.get(name, default)


def _cache_set(name, value, ttl=300):  # keep 5 minutes by default
    cache.set(name, value, ttl)


@login_required
def api_client_metrics(request):
    """
    ...existing docstring...
      ?granularity=hourly|daily|weekly   (related parts CTR)
      ?diagPeriod=daily|hourly           (avg steps & time)
      ?diyPeriod=daily|hourly            (DIY trend)
    """
    license_key = request.GET.get("licenseKey") or None
    period      = request.GET.get("period", "all")
    date_range  = request.GET.get("dateRange") or None
    granularity = request.GET.get("granularity", "daily")
    diag_period = request.GET.get("diagPeriod", "daily")
    diy_period  = request.GET.get("diyPeriod", "daily")   # <-- NEW

    from django.core.cache import cache
    def _cache_get(name, default): return cache.get(name, default)
    def _cache_set(name, value, ttl=300): cache.set(name, value, ttl)

    def _safe(fetch_fn, cache_key, fallback):
        try:
            data = fetch_fn()
            _cache_set(cache_key, data, ttl=300)
            return data
        except Exception:
            return _cache_get(cache_key, fallback)

    # cache keys
    k_users   = "last_good::user_chart"
    k_verifs  = f"last_good::verify_chart::{license_key}"
    k_support = f"last_good::support_chart::{license_key}"
    k_threads = f"last_good::chat_thread_chart::{license_key}"
    k_recents = f"last_good::recent_activities::{license_key}"
    k_days    = f"last_good::most_active_days::{period}::{license_key}"
    k_hours   = f"last_good::most_active_hours::{period}::{license_key}"
    k_topcars = f"last_good::top_car_diagnoses::{license_key}::{date_range}"
    k_rpcr    = f"last_good::related_parts_click_rate::{granularity}::{license_key}"
    k_parts   = f"last_good::parts_stats::{license_key}"
    k_steps   = f"last_good::avg_steps_per_diagnosis::{diag_period}::{license_key}"
    k_time    = f"last_good::avg_diagnosis_time::{diag_period}::{license_key}"
    k_diy     = f"last_good::diy_trend::{diy_period}::{license_key}"          # <-- NEW
    k_reasons = f"last_good::top_problem_reasons::{date_range}::{license_key}"# <-- NEW

    users   = _safe(lambda: fetch_lott_users_last5(), k_users, [])
    verifs  = _safe(lambda: fetch_lott_verifications_last5(license_key), k_verifs, [])
    support = _safe(lambda: fetch_support_last5(license_key), k_support, [])
    threads = _safe(lambda: fetch_chat_threads_last5(license_key), k_threads, [])
    recents = _safe(lambda: fetch_recent_activities(license_key=license_key), k_recents, [])
    weekdays= _safe(lambda: fetch_most_active_days(period=period, license_key=license_key), k_days, [])
    hours   = _safe(lambda: fetch_most_active_hours(period=period, license_key=license_key), k_hours,
                    {"period": "all", "totalDistinctUsers": 0,
                     "perHour": [{"hour": h, "distinctUsers": 0} for h in range(24)]})
    topcars = _safe(lambda: fetch_top_car_diagnoses(license_key=license_key, date_range=date_range),
                    k_topcars, {"top5Makes": [], "top5Models": []})
    rp_click= _safe(lambda: fetch_related_parts_click_rate(granularity, license_key), k_rpcr, [])
    parts   = _safe(lambda: fetch_parts_stats(license_key), k_parts, [])

    avg_steps = _safe(lambda: fetch_avg_steps_per_diagnosis(diag_period, license_key), k_steps, [])
    avg_time  = _safe(lambda: fetch_avg_diagnosis_time(diag_period, license_key), k_time, [])

    diy_trend = _safe(lambda: fetch_diy_trend(period=diy_period, license_key=license_key), k_diy, [])   # <-- FIX
    prob_reas = _safe(lambda: fetch_top_problem_reasons(license_key=license_key, date_range=date_range),
                      k_reasons, {"highPriority": [], "lowPriority": []})                                # <-- FIX

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
            "avg_steps_per_diagnosis": avg_steps,
            "avg_diagnosis_time": avg_time,
            "diy_trend": diy_trend,
            "top_problem_reasons": prob_reas,
        }
    })
