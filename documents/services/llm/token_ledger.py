from __future__ import annotations
from dataclasses import dataclass
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime

def _today():
    return timezone.localdate().isoformat()

def _seconds_until_tomorrow() -> int:
    tz = timezone.get_current_timezone()
    now = timezone.localtime(timezone.now(), tz)
    tomorrow = (now + timedelta(days=1)).date()
    next_midnight = timezone.make_aware(datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0), tz)
    return max(1, int((next_midnight - now).total_seconds()))

def _normalize_purpose(purpose: str) -> str:
    p = (purpose or "").strip().lower()
    if p == "chat_stream":
        return "chat"  # รวม stream เข้ากับ chat (ปรับได้)
    return p or "chat"

def _key_total(user_id: int, purpose: str) -> str:
    return f"llm_tokens:{user_id}:{_today()}:{_normalize_purpose(purpose)}:total"

def budget_for(purpose: str) -> int:
    budgets = getattr(settings, "LLM_TOKEN_BUDGETS", {}) or {}
    return int(budgets.get(_normalize_purpose(purpose), budgets.get("chat", 0)) or 0)

def get_spent(user_id: int, purpose: str) -> int:
    return int(cache.get(_key_total(user_id, purpose), 0) or 0)

def get_remaining(user_id: int, purpose: str) -> int:
    b = budget_for(purpose)
    return max(0, b - get_spent(user_id, purpose))

def can_spend(user_id: int, purpose: str, est_tokens: int) -> bool:
    # กันไว้ก่อนยิงจริง (estimate)
    return get_remaining(user_id, purpose) >= max(1, int(est_tokens))

def spend(user_id: int, purpose: str, tokens: int):
    # อัปเดตหลังรู้ tokens จริง
    ttl = _seconds_until_tomorrow()
    key = _key_total(user_id, purpose)
    cache.add(key, 0, timeout=ttl)
    try:
        cache.incr(key, int(tokens))
    except ValueError:
        cache.set(key, int(tokens), timeout=ttl)

@dataclass
class PurposeStatus:
    purpose: str
    budget: int
    spent: int
    remaining: int
    ratio_remaining: float

def get_all_status(user_id: int) -> list[PurposeStatus]:
    budgets = getattr(settings, "LLM_TOKEN_BUDGETS", {}) or {}
    out = []
    for p, b in budgets.items():
        p2 = _normalize_purpose(p)
        spent = get_spent(user_id, p2)
        budget = int(b or 0)
        remaining = max(0, budget - spent)
        ratio = (remaining / budget) if budget > 0 else 0.0
        out.append(PurposeStatus(p2, budget, spent, remaining, ratio))
    # รวม purpose ซ้ำ (ถ้าตั้งทั้ง chat และ chat_stream) ให้เหลือ unique
    uniq = {}
    for s in out:
        if s.purpose not in uniq:
            uniq[s.purpose] = s
        else:
            # เอา budget ที่มากกว่า หรือ sum ตามที่ต้องการ
            prev = uniq[s.purpose]
            uniq[s.purpose] = PurposeStatus(
                s.purpose,
                max(prev.budget, s.budget),
                max(prev.spent, s.spent),
                max(prev.remaining, s.remaining),
                max(prev.ratio_remaining, s.ratio_remaining),
            )
    return sorted(uniq.values(), key=lambda x: x.purpose)
