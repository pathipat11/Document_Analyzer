from django.contrib import admin
from .models import Document

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "file_name", "document_type", "word_count", "uploaded_at")
    list_filter = ("document_type", "uploaded_at")
    search_fields = ("file_name", "summary")
    readonly_fields = ("word_count", "char_count", "uploaded_at")

    fieldsets = (
        ("File", {"fields": ("file", "file_name", "file_ext", "mime_type")}),
        ("Analysis", {"fields": ("document_type", "summary", "word_count", "char_count")}),
        ("Text", {"fields": ("extracted_text",)}),
        ("System", {"fields": ("uploaded_at",)}),
    )
