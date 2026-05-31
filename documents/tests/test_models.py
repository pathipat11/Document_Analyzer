from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from documents.models import CombinedSummary, Conversation, Document

User = get_user_model()


class ConversationConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="conv", password="pw")
        cls.doc = Document.objects.create(
            owner=cls.user, file_name="d.txt", file_ext="txt"
        )
        cls.nb = CombinedSummary.objects.create(owner=cls.user, title="NB")

    def test_document_only_is_valid(self):
        conv = Conversation.objects.create(owner=self.user, document=self.doc)
        self.assertEqual(conv.document_id, self.doc.id)

    def test_notebook_only_is_valid(self):
        conv = Conversation.objects.create(owner=self.user, notebook=self.nb)
        self.assertEqual(conv.notebook_id, self.nb.id)

    def test_both_targets_is_invalid(self):
        with self.assertRaises(ValidationError):
            Conversation.objects.create(
                owner=self.user, document=self.doc, notebook=self.nb
            )

    def test_no_target_is_invalid(self):
        with self.assertRaises(ValidationError):
            Conversation.objects.create(owner=self.user)
