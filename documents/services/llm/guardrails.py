from django.core.cache import cache
from django.conf import settings
from datetime import date

def check_daily_limit(user_id: int) -> bool:
    key = f"llm_calls:{user_id}:{date.today().isoformat()}"
    n = cache.get(key, 0)
    limit = getattr(settings, "LLM_DAILY_CALL_LIMIT", 200)
    return n < limit

def incr_daily_limit(user_id: int):
    key = f"llm_calls:{user_id}:{date.today().isoformat()}"
    cache.add(key, 0, timeout=60*60*24)
    cache.incr(key)
