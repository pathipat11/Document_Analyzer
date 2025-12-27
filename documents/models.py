from django.conf import settings
from django.db import models

class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    
    file = models.FileField(upload_to="documents/")
    file_name = models.CharField(max_length=255)
    file_ext = models.CharField(max_length=20, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)

    extracted_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    word_count = models.IntegerField(default=0)
    char_count = models.IntegerField(default=0)

    document_type = models.CharField(max_length=50, default="other")

    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.file_name

class CombinedSummary(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="combined_summaries",
    )
    documents = models.ManyToManyField(Document, related_name="combined_in")

    title = models.CharField(max_length=200, default="Combined Summary")
    combined_summary = models.TextField(blank=True)

    # optional metadata
    doc_count = models.IntegerField(default=0)
    total_words = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.doc_count} docs)"