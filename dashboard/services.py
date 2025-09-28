import requests
from typing import Dict, Any, List, Optional

# ---- Hard-coded config (you said no env vars for now) ----
EXT_API_BASE = "http://dev-api-service.mechconnect.de/api"
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "Admin@123"

# Simple in-memory token cache for this process
_TOKEN: str | None = None


def _login_and_get_token() -> str:
    """
    Log in to the external API and return a JWT token.
    Keeps it simple: just request and store in module memory.
    """
    global _TOKEN
    url = f"{EXT_API_BASE}/admin/auth/login"
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    j = r.json()
    token = j.get("payload", {}).get("token")
    if not token:
        raise RuntimeError("External login did not return a token.")
    _TOKEN = token
    return token


def _auth_headers() -> Dict[str, str]:
    """
    Return auth headers; log in if we don't have a token yet.
    """
    global _TOKEN
    if not _TOKEN:
        _login_and_get_token()
    return {"Authorization": f"Bearer {_TOKEN}"}


def fetch_license_key_stats() -> Dict[str, Any]:
    """
    GET /admin/dashboard/license-key-data
    Returns a simple shape for the frontend:
    {
      "new": int, "active": int, "inactive": int, "total": int
    }
    Retries login once on 401.
    """
    global _TOKEN
    url = f"{EXT_API_BASE}/admin/dashboard/license-key-data"

    # First attempt with current token (or after auto-login)
    headers = _auth_headers()
    r = requests.get(url, headers=headers, timeout=15)

    # If token expired/invalid, re-login once
    if r.status_code == 401:
        _TOKEN = None
        headers = _auth_headers()
        r = requests.get(url, headers=headers, timeout=15)

    r.raise_for_status()
    j = r.json()

    # API returns:
    # {
    #   "isSuccess": true,
    #   "statusCode": 200,
    #   "message": "...",
    #   "newUsers": 3,
    #   "activeUser": 3,
    #   "inactiveUser": 0
    # }

    new_val = int(j.get("newUsers") or 0)
    active_val = int(j.get("activeUser") or 0)
    inactive_val = int(j.get("inactiveUser") or 0)
    total = new_val + active_val + inactive_val

    return {
        "new": new_val,
        "active": active_val,
        "inactive": inactive_val,
        "total": total,
    }


def _authed_get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    """GET with auth; retry login once on 401."""
    global _TOKEN
    headers = _auth_headers()
    r = requests.get(url, headers=headers, params=params or {}, timeout=20)
    if r.status_code == 401:
        _TOKEN = None
        headers = _auth_headers()
        r = requests.get(url, headers=headers, params=params or {}, timeout=20)
    r.raise_for_status()
    return r


# ---------------- Lott.de metrics ----------------

def fetch_lott_users_last5() -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/user-chart
    Returns list of objects: [{"month":"May","total":0}, ...]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/user-chart"
    r = _authed_get(url)
    j = r.json() or {}
    payload = j.get("payload") or []
    # Normalize: only take 'month' and 'total'
    normalized = [{"month": item.get("month"), "total": int(
        item.get("total") or 0)} for item in payload]
    return normalized


def fetch_lott_verifications_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/car-part-verify-chart(?licenseKey=...)
    Returns list of objects: [{"month":"May","total":0}, ...]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/car-part-verify-chart"
    params = {"licenseKey": license_key} if license_key else None
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    normalized = [{"month": item.get("month"), "total": int(
        item.get("total") or 0)} for item in payload]
    return normalized


# ... keep existing imports and helpers at the top ...

def fetch_support_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/support-chart(?licenseKey=...)
    Returns [{"month":"May","total":0}, ...]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/support-chart"
    params = {"licenseKey": license_key} if license_key else None
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_chat_threads_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/chat-thread-chart(?licenseKey=...)
    Returns [{"month":"May","total":0}, ...]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/chat-thread-chart"
    params = {"licenseKey": license_key} if license_key else None
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_recent_activities(limit: int = 5, license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/recent-activities
    Returns a list of recent items across modules (we'll keep top 5).
    """
    url = f"{EXT_API_BASE}/admin/dashboard/recent-activities"
    # API returns 5 already, but we allow future flexibility
    params = {"licenseKey": license_key} if license_key else None
    r = _authed_get(url, params=params)
    j = r.json() or {}
    acts = j.get("activities") or []
    # normalize (defensive)
    if limit and isinstance(acts, list):
        acts = acts[:limit]
    return acts


def fetch_most_active_days(period: str = "all", license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /api/admin/dashboard/get-most-active-days(?period=all|am|pm&licenseKey=...)
    Returns [{dayOfWeek, distinctUsers, totalConversations}, ...]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-most-active-days"
    params: Dict[str, Any] = {"period": period}
    if license_key:
        params["licenseKey"] = license_key
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    # normalize: ensure ints
    norm = []
    for p in payload:
        norm.append({
            "dayOfWeek": p.get("dayOfWeek"),
            "distinctUsers": int(p.get("distinctUsers") or 0),
            "totalConversations": int(p.get("totalConversations") or 0),
        })
    return norm


def fetch_most_active_hours(period: str = "all", license_key: Optional[str] = None) -> Dict[str, Any]:
    """
    GET /api/admin/dashboard/get-most-active-hours(?period=all|am|pm&licenseKey=...)
    Expected shape:
    {
      "period": "all",
      "totalDistinctUsers": 6,
      "perHour": [{"hour":0,"distinctUsers":0}, ...]
    }
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-most-active-hours"
    params: Dict[str, Any] = {"period": period}
    if license_key:
        params["licenseKey"] = license_key
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or {}
    # Normalize
    per_hour = payload.get("perHour") or []
    norm = {
        "period": payload.get("period") or period,
        "totalDistinctUsers": int(payload.get("totalDistinctUsers") or 0),
        "perHour": [
            {"hour": int(p.get("hour") or 0), "distinctUsers": int(
                p.get("distinctUsers") or 0)}
            for p in per_hour
        ]
    }
    # Ensure all 24 hours present (0..23) even if API returns sparse data
    if len(norm["perHour"]) < 24:
        seen = {ph["hour"]: ph for ph in norm["perHour"]}
        norm["perHour"] = [{"hour": h, "distinctUsers": seen.get(h, {"distinctUsers": 0}).get("distinctUsers", 0)}
                           for h in range(24)]
    return norm


def fetch_top_car_diagnoses(license_key: Optional[str] = None,
                            date_range: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    GET /api/admin/dashboard/get-top-car-diagnoses(?licenseKey=...&dateRange=7d|1m|1y)
    Returns:
    {
      "top5Makes": [{"make":"AUDI","count":2}, ...],
      "top5Models":[{"model":"A3 ...","count":2}, ...]
    }
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-top-car-diagnoses"
    params: Dict[str, Any] = {}
    if license_key:
        params["licenseKey"] = license_key
    if date_range:
        params["dateRange"] = date_range
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or {}
    makes = payload.get("top5Makes") or []
    models = payload.get("top5Models") or []
    # Normalize integers
    makes = [{"make": m.get("make") or "—", "count": int(
        m.get("count") or 0)} for m in makes]
    models = [{"model": m.get("model") or "—", "count": int(
        m.get("count") or 0)} for m in models]
    return {"top5Makes": makes, "top5Models": models}


# -------- FIXED FETCHERS --------
def fetch_related_parts_click_rate(granularity: str = "daily",
                                   license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /admin/dashboard/get-related-parts-click-rate?granularity=hourly|daily|weekly[&licenseKey=...]
    Returns a list of points; we keep API fields as-is.
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-related-parts-click-rate"  # <-- removed extra /api
    params: Dict[str, Any] = {"granularity": granularity}
    if license_key:
        params["licenseKey"] = license_key
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    # normalize numerics defensively
    for p in payload:
        if "clickRate" in p and p["clickRate"] is not None:
            try:
                p["clickRate"] = float(p["clickRate"])
            except Exception:
                p["clickRate"] = 0.0
    return payload

def fetch_parts_stats(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /admin/dashboard/get-parts-stats[?licenseKey=...]
    Returns [{"label":"Verified Parts","count":n}, {"label":"Rejected Parts","count":m}]
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-parts-stats"  # <-- removed extra /api
    params: Dict[str, Any] = {}
    if license_key:
        params["licenseKey"] = license_key
    r = _authed_get(url, params=params)
    j = r.json() or {}
    payload = j.get("payload") or []
    # ensure count is int
    return [{"label": p.get("label") or "—", "count": int(p.get("count") or 0)} for p in payload]