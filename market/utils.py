from .models import AnalyticsEvent

def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

# Plug your GeoIP provider here and return dict with keys: country, region, city, lat, lon
def lookup_geo(ip: str) -> dict:
    return {}

def record_event(request, *, event_type, product=None, negotiation=None, extra=None):
    ip = get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")
    ref = request.META.get("HTTP_REFERER", "")
    geo = lookup_geo(ip) if ip else {}
    return AnalyticsEvent.objects.create(
        event_type=event_type,
        user=request.user if request.user.is_authenticated else None,
        product=product,
        negotiation=negotiation,
        ip=ip,
        user_agent=ua,
        referrer=ref,
        country=geo.get("country", ""),
        region=geo.get("region", ""),
        city=geo.get("city", ""),
        lat=geo.get("lat"),
        lon=geo.get("lon"),
        extra=extra or {},
    )
