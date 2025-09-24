from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Organization

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