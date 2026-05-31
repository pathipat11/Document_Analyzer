from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from documents.models import Document

User = get_user_model()


class StatusApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="status", password="pw")
        cls.other = User.objects.create_user(username="other", password="pw")
        cls.doc = Document.objects.create(
            owner=cls.user, file_name="d.txt", file_ext="txt",
            status="processing", word_count=10, char_count=50,
        )
        cls.done = Document.objects.create(
            owner=cls.user, file_name="e.txt", file_ext="txt",
            status="done", document_type="report", summary="x",
        )
        cls.foreign = Document.objects.create(
            owner=cls.other, file_name="f.txt", file_ext="txt", status="queued",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _url(self):
        return reverse("documents:status_api")

    def test_requires_login(self):
        self.client.logout()
        res = self.client.get(self._url(), {"ids": str(self.doc.id)})
        self.assertEqual(res.status_code, 302)

    def test_returns_status_for_owned_docs(self):
        res = self.client.get(self._url(), {"ids": f"{self.doc.id},{self.done.id}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        by_id = {i["id"]: i for i in data["items"]}
        self.assertEqual(by_id[self.doc.id]["status"], "processing")
        self.assertEqual(by_id[self.done.id]["status"], "done")
        self.assertTrue(by_id[self.done.id]["has_summary"])
        self.assertEqual(by_id[self.done.id]["document_type"], "report")

    def test_excludes_other_users_documents(self):
        res = self.client.get(self._url(), {"ids": str(self.foreign.id)})
        data = res.json()
        self.assertEqual(data["items"], [])

    def test_empty_ids_returns_empty(self):
        res = self.client.get(self._url(), {"ids": ""})
        self.assertEqual(res.json()["items"], [])

    def test_ignores_non_numeric_ids(self):
        res = self.client.get(self._url(), {"ids": "abc,," + str(self.doc.id)})
        data = res.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], self.doc.id)
