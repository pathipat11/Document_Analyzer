from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime

def _today_key(user_id: int) -> str:
    today = timezone.localdate()
    return f"llm_calls:{user_id}:{today.isoformat()}"

def _seconds_until_tomorrow() -> int:
    tz = timezone.get_current_timezone()
    now = timezone.localtime(timezone.now(), tz)
    tomorrow = (now + timedelta(days=1)).date()
    next_midnight = timezone.make_aware(
        datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0),
        tz
    )
    return max(1, int((next_midnight - now).total_seconds()))

def check_daily_limit(user_id: int) -> bool:
    key = _today_key(user_id)
    n = cache.get(key, 0)
    limit = int(getattr(settings, "LLM_DAILY_CALL_LIMIT", 200))
    return n < limit

def incr_daily_limit(user_id: int):
    key = _today_key(user_id)
    ttl = _seconds_until_tomorrow()
    # ตั้งค่าเริ่มต้น + TTL ให้ตรงกับเที่ยงคืน
    cache.add(key, 0, timeout=ttl)
    try:
        cache.incr(key)
    except ValueError:
        # บาง backend อาจต้อง set ก่อน
        cache.set(key, 1, timeout=ttl)
