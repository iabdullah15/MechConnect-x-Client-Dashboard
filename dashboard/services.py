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



from django.core.cache import cache

_TOKEN: str | None = None


def _login_and_get_token() -> str:
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
    global _TOKEN
    if not _TOKEN:
        _login_and_get_token()
    return {"Authorization": f"Bearer {_TOKEN}"}


def _cache_key(url: str, params: Optional[Dict[str, Any]]) -> str:
    # Stable key from url + sorted params
    p = params or {}
    try:
        packed = json.dumps(sorted(p.items()), separators=(",", ":"), ensure_ascii=True)
    except Exception:
        packed = str(sorted(p.items()))
    return f"extjson::{url}::{packed}"


def _authed_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    ttl_seconds: Optional[int] = 60,
    retries: int = 5,                 # was 3
    timeout: int = 20,
) -> Dict[str, Any]:
    ck = _cache_key(url, params)
    if ttl_seconds and (cached := cache.get(ck)) is not None:
        return cached

    global _TOKEN
    attempt = 0
    while True:
        attempt += 1
        headers = _auth_headers()
        r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)

        if r.status_code == 401:
            _TOKEN = None
            headers = _auth_headers()
            r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)

        if r.status_code in (429, 502, 503, 504):
            if attempt >= retries:
                r.raise_for_status()
            retry_after = r.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep_for = float(retry_after)
                except Exception:
                    sleep_for = 2.0
            else:
                # exponential backoff with jitter, capped
                base = min(2 ** (attempt - 1), 16)
                sleep_for = base + random.uniform(0, 0.5)
            time.sleep(sleep_for)
            continue

        r.raise_for_status()
        j = r.json() or {}
        if ttl_seconds:
            cache.set(ck, j, ttl_seconds)
        return j


# ---------------- Lott.de metrics ----------------

def fetch_lott_users_last5() -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/user-chart"
    j = _authed_get_json(url, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_lott_verifications_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/car-part-verify-chart"
    params = {"licenseKey": license_key} if license_key else None
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_support_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/support-chart"
    params = {"licenseKey": license_key} if license_key else None
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_chat_threads_last5(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/chat-thread-chart"
    params = {"licenseKey": license_key} if license_key else None
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{"month": p.get("month"), "total": int(p.get("total") or 0)} for p in payload]


def fetch_recent_activities(limit: int = 5, license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/recent-activities"
    params = {"licenseKey": license_key} if license_key else None
    j = _authed_get_json(url, params=params, ttl_seconds=30)
    acts = j.get("activities") or []
    return acts[:limit] if isinstance(acts, list) else []


def fetch_most_active_days(period: str = "all", license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/get-most-active-days"
    params: Dict[str, Any] = {"period": period}
    if license_key: params["licenseKey"] = license_key
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{
        "dayOfWeek": p.get("dayOfWeek"),
        "distinctUsers": int(p.get("distinctUsers") or 0),
        "totalConversations": int(p.get("totalConversations") or 0),
    } for p in payload]


def fetch_most_active_hours(period: str = "all", license_key: Optional[str] = None) -> Dict[str, Any]:
    url = f"{EXT_API_BASE}/admin/dashboard/get-most-active-hours"
    params: Dict[str, Any] = {"period": period}
    if license_key: params["licenseKey"] = license_key
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or {}
    per_hour = payload.get("perHour") or []
    norm = {
        "period": payload.get("period") or period,
        "totalDistinctUsers": int(payload.get("totalDistinctUsers") or 0),
        "perHour": [
            {"hour": int(p.get("hour") or 0), "distinctUsers": int(p.get("distinctUsers") or 0)}
            for p in per_hour
        ]
    }
    if len(norm["perHour"]) < 24:
        seen = {ph["hour"]: ph for ph in norm["perHour"]}
        norm["perHour"] = [{"hour": h, "distinctUsers": seen.get(h, {"distinctUsers": 0}).get("distinctUsers", 0)}
                           for h in range(24)]
    return norm


def fetch_top_car_diagnoses(license_key: Optional[str] = None,
                            date_range: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    url = f"{EXT_API_BASE}/admin/dashboard/get-top-car-diagnoses"
    params: Dict[str, Any] = {}
    if license_key: params["licenseKey"] = license_key
    if date_range: params["dateRange"] = date_range
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or {}
    makes = payload.get("top5Makes") or []
    models = payload.get("top5Models") or []
    makes = [{"make": m.get("make") or "—", "count": int(m.get("count") or 0)} for m in makes]
    models = [{"model": m.get("model") or "—", "count": int(m.get("count") or 0)} for m in models]
    return {"top5Makes": makes, "top5Models": models}


def fetch_related_parts_click_rate(granularity: str = "daily",
                                   license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/get-related-parts-click-rate"
    params: Dict[str, Any] = {"granularity": granularity}
    if license_key: params["licenseKey"] = license_key
    j = _authed_get_json(url, params=params, ttl_seconds=30)
    payload = j.get("payload") or []
    for p in payload:
        if "clickRate" in p and p["clickRate"] is not None:
            try: p["clickRate"] = float(p["clickRate"])
            except Exception: p["clickRate"] = 0.0
    return payload


def fetch_parts_stats(license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = f"{EXT_API_BASE}/admin/dashboard/get-parts-stats"
    params: Dict[str, Any] = {"licenseKey": license_key} if license_key else None
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or []
    return [{"label": p.get("label") or "—", "count": int(p.get("count") or 0)} for p in payload]


# --- add near your other imports if not present ---
import re

# --- NEW: Avg steps per diagnosis ---
def fetch_avg_steps_per_diagnosis(
    period: str = "daily",
    license_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    GET /admin/dashboard/get-avg-steps-per-diagnosis?period=daily|hourly[&licenseKey=...]
    Returns a list like: [{"date":"YYYY-MM-DD","avgStepsPerDiagnosis":2.86}, ...]
    We coerce avgStepsPerDiagnosis -> float defensively.
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-avg-steps-per-diagnosis"
    params: Dict[str, Any] = {"period": period}
    if license_key:
        params["licenseKey"] = license_key

    j = _authed_get_json(url, params=params, ttl_seconds=30)
    payload = j.get("payload") or []
    for p in payload:
        try:
            p["avgStepsPerDiagnosis"] = float(p.get("avgStepsPerDiagnosis") or 0.0)
        except Exception:
            p["avgStepsPerDiagnosis"] = 0.0
    return payload


# --- NEW: Avg diagnosis time (minutes) ---
def fetch_avg_diagnosis_time(
    period: str = "daily",
    license_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    GET /admin/dashboard/get-avg-diagnosis-time?period=daily|hourly[&licenseKey=...]
    API returns avgDiagnosisTimeMinutes as a string like "3.42 Minutes".
    We keep the original field and also add a numeric 'minutes' for charting.
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-avg-diagnosis-time"
    params: Dict[str, Any] = {"period": period}
    if license_key:
        params["licenseKey"] = license_key

    j = _authed_get_json(url, params=params, ttl_seconds=30)
    payload = j.get("payload") or []

    for p in payload:
        raw = p.get("avgDiagnosisTimeMinutes", "")
        # extract leading float, e.g., "3.42 Minutes" -> 3.42
        try:
            m = re.search(r"[-+]?\d*\.?\d+", str(raw) or "")
            minutes = float(m.group(0)) if m else 0.0
        except Exception:
            minutes = 0.0
        p["minutes"] = minutes
    return payload


# --- NEW: DIY trend ---
def fetch_diy_trend(period: str = "daily", license_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    GET /admin/dashboard/get-diy-trend?period=daily|hourly[&licenseKey=...]
    Returns a list of points with {totalUsers, engagedUsers, clickRate, date|hour|_id}
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-diy-trend"
    params: Dict[str, Any] = {"period": period}
    if license_key:
        params["licenseKey"] = license_key
    j = _authed_get_json(url, params=params, ttl_seconds=30)
    payload = j.get("payload") or []
    # normalize numerics defensively
    out = []
    for p in payload:
        out.append({
            "date": p.get("date"),
            "hour": p.get("hour"),
            "_id": p.get("_id"),
            "totalUsers": int(p.get("totalUsers") or 0),
            "engagedUsers": int(p.get("engagedUsers") or 0),
            "clickRate": float(p.get("clickRate") or 0),
        })
    return out


# --- NEW: Top problem reasons ---
def fetch_top_problem_reasons(license_key: Optional[str] = None,
                              date_range: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    GET /admin/dashboard/get-top-problem-reasons[?dateRange=7d|1m|1y&licenseKey=...]
    Returns:
    {
      "highPriority": [{"title":"..","count":n}, ...],
      "lowPriority": [{"title":"..","count":n}, ...]
    }
    """
    url = f"{EXT_API_BASE}/admin/dashboard/get-top-problem-reasons"
    params: Dict[str, Any] = {}
    if license_key:
        params["licenseKey"] = license_key
    if date_range:
        params["dateRange"] = date_range
    j = _authed_get_json(url, params=params, ttl_seconds=60)
    payload = j.get("payload") or {}
    high = payload.get("highPriority") or []
    low  = payload.get("lowPriority") or []
    # normalize
    high = [{"title": x.get("title") or "—", "count": int(x.get("count") or 0)} for x in high]
    low  = [{"title": x.get("title") or "—", "count": int(x.get("count") or 0)} for x in low]
    return {"highPriority": high, "lowPriority": low}
