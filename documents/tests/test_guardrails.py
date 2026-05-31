from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from documents.services.llm.guardrails import check_daily_limit, incr_daily_limit
from documents.services.llm import token_ledger


LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "guardrail-tests",
    }
}


@override_settings(CACHES=LOCMEM)
class DailyLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(LLM_DAILY_CALL_LIMIT=0)
    def test_zero_limit_means_unlimited(self):
        for _ in range(5):
            incr_daily_limit(1, "chat")
        self.assertTrue(check_daily_limit(1, "chat"))

    @override_settings(LLM_DAILY_CALL_LIMIT=3)
    def test_limit_is_enforced_after_threshold(self):
        self.assertTrue(check_daily_limit(1, "chat"))
        for _ in range(3):
            incr_daily_limit(1, "chat")
        # Used 3 of 3 -> next call should be blocked.
        self.assertFalse(check_daily_limit(1, "chat"))

    @override_settings(LLM_DAILY_CALL_LIMIT=2)
    def test_chat_and_upload_counted_separately(self):
        incr_daily_limit(1, "chat")
        incr_daily_limit(1, "chat")
        # chat is exhausted...
        self.assertFalse(check_daily_limit(1, "chat"))
        # ...but upload (summarize/classify map to "upload") is untouched.
        self.assertTrue(check_daily_limit(1, "summarize"))

    @override_settings(LLM_DAILY_CALL_LIMIT=2)
    def test_users_counted_separately(self):
        incr_daily_limit(1, "chat")
        incr_daily_limit(1, "chat")
        self.assertFalse(check_daily_limit(1, "chat"))
        self.assertTrue(check_daily_limit(2, "chat"))


@override_settings(CACHES=LOCMEM)
class TokenLedgerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_normalize_purpose(self):
        self.assertEqual(token_ledger._normalize_purpose("chat"), "chat")
        self.assertEqual(token_ledger._normalize_purpose("chat_stream"), "chat")
        self.assertEqual(token_ledger._normalize_purpose("summarize"), "upload")
        self.assertEqual(token_ledger._normalize_purpose("classify"), "upload")
        self.assertEqual(token_ledger._normalize_purpose("combined"), "upload")
        self.assertEqual(token_ledger._normalize_purpose("unknown"), "chat")

    @override_settings(LLM_TOKEN_BUDGETS={"chat": 100, "upload": 200})
    def test_spend_and_remaining(self):
        self.assertEqual(token_ledger.get_remaining(1, "chat"), 100)
        token_ledger.spend(1, "chat", 30)
        self.assertEqual(token_ledger.get_spent(1, "chat"), 30)
        self.assertEqual(token_ledger.get_remaining(1, "chat"), 70)

    @override_settings(LLM_TOKEN_BUDGETS={"chat": 100, "upload": 200})
    def test_can_spend_respects_remaining(self):
        token_ledger.spend(1, "chat", 95)
        self.assertTrue(token_ledger.can_spend(1, "chat", 5))
        self.assertFalse(token_ledger.can_spend(1, "chat", 6))

    @override_settings(LLM_TOKEN_BUDGETS={"chat": 100, "upload": 200})
    def test_purpose_aliases_share_budget(self):
        # summarize and classify both map to "upload".
        token_ledger.spend(1, "summarize", 50)
        token_ledger.spend(1, "classify", 50)
        self.assertEqual(token_ledger.get_spent(1, "upload"), 100)
        self.assertEqual(token_ledger.get_remaining(1, "upload"), 100)

    @override_settings(LLM_TOKEN_BUDGETS={"chat": 100, "upload": 200})
    def test_get_all_status_dedupes_by_purpose(self):
        statuses = token_ledger.get_all_status(1)
        purposes = sorted(s.purpose for s in statuses)
        self.assertEqual(purposes, ["chat", "upload"])
