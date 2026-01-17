from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime

def _today_key(user_id: int, purpose: str = "chat") -> str:
    today = timezone.localdate()
    purpose = (purpose or "chat").strip().lower()
    if purpose in ("chat_stream",):
        purpose = "chat"
    elif purpose in ("summarize", "classify", "title", "combined", "upload"):
        purpose = "upload"
    return f"llm_calls:{user_id}:{today.isoformat()}:{purpose}"

def _seconds_until_tomorrow() -> int:
    tz = timezone.get_current_timezone()
    now = timezone.localtime(timezone.now(), tz)
    tomorrow = (now + timedelta(days=1)).date()
    next_midnight = timezone.make_aware(
        datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0),
        tz
    )
    return max(1, int((next_midnight - now).total_seconds()))

def check_daily_limit(user_id: int, purpose: str = "chat") -> bool:
    limit = int(getattr(settings, "LLM_DAILY_CALL_LIMIT", 200))
    if limit <= 0:
        return True
    key = _today_key(user_id, purpose)
    n = cache.get(key, 0)
    return n < limit

def incr_daily_limit(user_id: int, purpose: str = "chat"):
    limit = int(getattr(settings, "LLM_DAILY_CALL_LIMIT", 200))
    if limit <= 0:
        return
    key = _today_key(user_id, purpose)
    ttl = _seconds_until_tomorrow()
    cache.add(key, 0, timeout=ttl)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ttl)
