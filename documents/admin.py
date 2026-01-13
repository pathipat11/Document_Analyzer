from django.contrib import admin
from .models import Document, CombinedSummary, Conversation, Message, LLMCallLog, DocumentChunk



@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id","file_name","status","document_type","word_count","uploaded_at","processed_at")
    list_filter = ("status","document_type","uploaded_at")
    search_fields = ("file_name", "summary", "extracted_text")
    readonly_fields = ("word_count", "char_count", "uploaded_at", "processed_at")


@admin.register(CombinedSummary)
class CombinedSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "doc_count", "total_words", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "combined_summary")
    readonly_fields = ("doc_count", "total_words", "created_at")
    filter_horizontal = ("documents",)  # เลือก docs ได้ง่ายขึ้น


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "created_at")
    fields = ("role", "content", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "document", "notebook", "created_at", "message_count")
    list_filter = ("created_at",)
    search_fields = ("title", "owner__username", "document__file_name", "notebook__title")
    readonly_fields = ("created_at",)
    inlines = [MessageInline]

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "short_content", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "conversation__title", "conversation__owner__username")
    readonly_fields = ("created_at",)

    def short_content(self, obj):
        t = obj.content or ""
        return t[:80] + ("…" if len(t) > 80 else "")
    short_content.short_description = "Content"

@admin.register(LLMCallLog)
class LLMCallLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "provider", "purpose", "ok", "latency_ms", "input_tokens", "output_tokens", "created_at")
    list_filter = ("provider", "purpose", "ok", "created_at")

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document_id", "idx", "created_at")
    search_fields = ("content",)