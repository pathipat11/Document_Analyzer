import csv
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q

from .services.upload_validation import validate_files, get_limits
from .services.combined_summarizer import build_combined_summary, build_combined_title_and_summary
from .services.processor import process_document
from .services.chat_service import answer_chat
from .models import Document, CombinedSummary, Conversation, Message

def health(request):
    return JsonResponse({"status": "ok"})

@login_required
def upload_document(request):
    limits = get_limits()

    if request.method == "POST":
        files = request.FILES.getlist("files")
        auto_combine = request.POST.get("auto_combine") == "1"
        title = (request.POST.get("notebook_title") or "").strip()

        try:
            validate_files(files)
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, "documents/upload.html", {"limits": limits})

        created: list[Document] = []
        for f in files:
            ext = Path(f.name).suffix.lower().lstrip(".")
            mime = getattr(f, "content_type", "") or ""

            doc = Document.objects.create(
                owner=request.user,
                file=f,
                file_name=f.name,
                file_ext=ext,
                mime_type=mime,
            )
            process_document(doc)
            created.append(doc)

        if auto_combine and len(created) >= 2:
            ai_title, combined_text = build_combined_title_and_summary(created)
            final_title = title or ai_title

            cs = CombinedSummary.objects.create(
                owner=request.user,
                title=final_title,
                combined_summary=combined_text,
                doc_count=len(created),
                total_words=sum(d.word_count for d in created),
            )

            cs.documents.set(created)

            messages.success(request, f"Uploaded {len(created)} files and created a combined summary.")
            return redirect("documents:combined_detail", pk=cs.pk)

        messages.success(request, f"Uploaded and processed {len(created)} file(s).")
        if len(created) == 1:
            return redirect("documents:detail", pk=created[0].pk)
        return redirect("documents:list")

    return render(request, "documents/upload.html", {"limits": limits})


@login_required
def document_detail(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)
    return render(request, "documents/detail.html", {"doc": doc})

@login_required
def document_list(request):
    dtype = (request.GET.get("type") or "").strip().lower()

    docs = Document.objects.filter(owner=request.user).order_by("-uploaded_at")
    if dtype:
        docs = docs.filter(document_type=dtype)

    type_choices = ["invoice","announcement","policy","proposal","report","research","resume","other"]

    return render(request, "documents/list.html", {
        "docs": docs,
        "dtype": dtype,
        "type_choices": type_choices,
    })

@login_required
def reprocess_document(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)
    process_document(doc)
    return redirect("documents:detail", pk=doc.pk)

@login_required
def export_documents_csv(request):
    dtype = (request.GET.get("type") or "").strip().lower()
    docs = Document.objects.filter(owner=request.user).order_by("-uploaded_at")
    if dtype:
        docs = docs.filter(document_type=dtype)

    resp = HttpResponse(content_type="text/csv")
    filename = "documents.csv" if not dtype else f"documents_{dtype}.csv"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(resp)
    writer.writerow(["id", "file_name", "document_type", "word_count", "char_count", "summary", "uploaded_at"])

    for d in docs:
        writer.writerow([
            d.id,
            d.file_name,
            d.document_type,
            d.word_count,
            d.char_count,
            (d.summary or "").replace("\n", " ").strip(),
            d.uploaded_at.isoformat(),
        ])

    return resp

@login_required
def create_combined_summary(request):
    
    if request.method != "POST":
        return redirect("documents:list")

    ids = request.POST.getlist("doc_ids")
    ids = [int(i) for i in ids if i.isdigit()]

    if len(ids) < 2:
        messages.error(request, "Please select at least 2 documents to combine.")
        return redirect("documents:list")

    docs = list(Document.objects.filter(owner=request.user, id__in=ids).order_by("-uploaded_at"))
    if len(docs) < 2:
        messages.error(request, "Selected documents not found.")
        return redirect("documents:list")

    title, combined_text = build_combined_title_and_summary(docs)

    cs = CombinedSummary.objects.create(
        owner=request.user,
        title=title,
        combined_summary=combined_text,
        doc_count=len(docs),
        total_words=sum(d.word_count for d in docs),
    )
    cs.documents.set(docs)

    messages.success(request, "Combined summary created.")
    return redirect("documents:combined_detail", pk=cs.pk)


@login_required
def combined_detail(request, pk: int):
    cs = get_object_or_404(CombinedSummary, pk=pk, owner=request.user)
    docs = cs.documents.all().order_by("-uploaded_at")
    return render(request, "documents/combined_detail.html", {"cs": cs, "docs": docs})


@login_required
def combined_list(request):
    items = CombinedSummary.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "documents/combined_list.html", {"items": items})

@login_required
def chat_document(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)
    conv, _ = Conversation.objects.get_or_create(owner=request.user, document=doc)
    if not conv.title:
        conv.title = f"Chat: {doc.file_name}"
        conv.save(update_fields=["title"])
    return redirect("documents:chat_view", conv_id=conv.id)

@login_required
def chat_notebook(request, pk: int):
    nb = get_object_or_404(CombinedSummary, pk=pk, owner=request.user)
    conv, _ = Conversation.objects.get_or_create(owner=request.user, notebook=nb)
    if not conv.title:
        conv.title = f"Chat: {nb.title}"
        conv.save(update_fields=["title"])
    return redirect("documents:chat_view", conv_id=conv.id)

@login_required
@require_http_methods(["GET", "POST"])
def chat_view(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id, owner=request.user)

    if request.method == "POST":
        user_text = (request.POST.get("message") or "").strip()
        if not user_text:
            return redirect("documents:chat_view", conv_id=conv.id)

        Message.objects.create(conversation=conv, role="user", content=user_text)

        assistant_text = answer_chat(conv, user_text) or "I couldn't generate a response."
        Message.objects.create(conversation=conv, role="assistant", content=assistant_text)

        return redirect("documents:chat_view", conv_id=conv.id)

    msgs = conv.messages.all()
    return render(request, "documents/chat.html", {
        "conv": conv,
        "chat_messages": msgs,
    })

@login_required
@require_POST
def chat_api(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id, owner=request.user)

    user_text = (request.POST.get("message") or "").strip()
    rid = (request.POST.get("request_id") or "").strip()

    if not user_text:
        return JsonResponse({"ok": False, "error": "Empty message"}, status=400)
    if not rid:
        return JsonResponse({"ok": False, "error": "Missing request_id"}, status=400)

    # Save user msg (ถ้าอยาก “cancel แล้วไม่เก็บ user ด้วย” ดูหมายเหตุด้านล่าง)
    user_msg = Message.objects.create(conversation=conv, role="user", content=user_text)

    assistant_text = answer_chat(conv, user_text) or "I couldn't generate a response."

    # ✅ ถ้าถูก cancel ระหว่างรอ LLM → ไม่ save assistant และตอบว่า canceled
    if cache.get(f"chat_cancel:{conv.id}:{rid}"):
        # ทางเลือก: ลบ user message ที่เพิ่งสร้างด้วย
        user_msg.delete()
        return JsonResponse({"ok": False, "canceled": True}, status=409)

    Message.objects.create(conversation=conv, role="assistant", content=assistant_text)

    return JsonResponse({
        "ok": True,
        "assistant": assistant_text,
        "created_at": timezone.now().strftime("%b. %d, %Y, %I:%M %p"),
    })
    
@login_required
@require_POST
def chat_cancel_api(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id, owner=request.user)
    rid = (request.POST.get("request_id") or "").strip()
    if not rid:
        return JsonResponse({"ok": False, "error": "Missing request_id"}, status=400)

    cache.set(f"chat_cancel:{conv.id}:{rid}", True, timeout=300)
    return JsonResponse({"ok": True})
