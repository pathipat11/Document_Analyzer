import os
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.timezone import now

def upload_to_document(instance, filename):
    owner_id = instance.owner_id or "anon"
    y = now().strftime("%Y")
    m = now().strftime("%m")
    return os.path.join("incoming", f"user_{owner_id}", y, m, filename)


class Document(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    
    file = models.FileField(upload_to=upload_to_document)
    file_name = models.CharField(max_length=255)
    file_ext = models.CharField(max_length=20, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)

    extracted_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)

    word_count = models.IntegerField(default=0)
    char_count = models.IntegerField(default=0)

    status = models.CharField(max_length=20, default="queued")
    error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

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
    
class Conversation(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    # target: เลือกอย่างใดอย่างหนึ่ง
    document = models.ForeignKey(
        "Document",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    notebook = models.ForeignKey(
        "CombinedSummary",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # บังคับ XOR: ต้องมี document หรือ notebook อย่างใดอย่างหนึ่งเท่านั้น
        has_doc = self.document_id is not None
        has_nb = self.notebook_id is not None
        if has_doc == has_nb:
            raise ValidationError("Conversation must have exactly one target: document OR notebook.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        target = self.document.file_name if self.document_id else self.notebook.title
        return f"Chat: {target}"


class Message(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
    
    
class LLMCallLog(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    provider = models.CharField(max_length=30, default="bedrock")  # bedrock/ollama
    model_id = models.CharField(max_length=255, blank=True)

    purpose = models.CharField(max_length=50, blank=True)  # chat / summarize / classify / title / combined
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    latency_ms = models.IntegerField(default=0)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        
        
class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    idx = models.IntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "idx")]
        ordering = ["idx"]

    def __str__(self):
        return f"{self.document_id}#{self.idx}"
