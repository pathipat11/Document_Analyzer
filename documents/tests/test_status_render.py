from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from documents.models import Document

User = get_user_model()


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class StatusRenderTests(TestCase):
    """Smoke tests that the polling hooks render in the list/detail pages."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="render", password="pw")
        cls.doc = Document.objects.create(
            owner=cls.user, file_name="r.txt", file_ext="txt", status="processing"
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_list_renders_status_hook(self):
        res = self.client.get(reverse("documents:list"))
        self.assertEqual(res.status_code, 200)
        # The list no longer shows an inline status pill; it carries a hidden
        # row marker that the polling script watches.
        self.assertContains(res, f'data-doc-id="{self.doc.id}"')
        self.assertContains(res, 'data-doc-status="processing"')
        self.assertNotContains(res, "doc-status-pill")

    def test_detail_renders_polling_hook(self):
        res = self.client.get(reverse("documents:detail", kwargs={"pk": self.doc.pk}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-detail-status="processing"')
        self.assertContains(res, f'data-doc-id="{self.doc.pk}"')
