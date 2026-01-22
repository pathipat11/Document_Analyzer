import csv, json, boto3, re
from pathlib import Path
from datetime import datetime, timedelta
from django.urls import reverse
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchHeadline
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q, Exists, OuterRef, Value, F
from django.db.models.functions import Coalesce
from urllib.parse import urlencode, quote

from documents.services.llm.token_ledger import get_all_status
from documents.services.upload.upload_validation import validate_files, get_limits
from documents.services.analysis.combined_summarizer import build_combined_summary, build_combined_title_and_summary
from documents.services.pipeline.processor import process_document
from documents.services.chat.chat_service import answer_chat, answer_chat_stream
from documents.services.llm.guardrails import check_daily_limit
from documents.services.llm.client import LLMError
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
            ai_title, combined_text = build_combined_title_and_summary(created, owner=request.user)
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
    q = (request.GET.get("q") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Document.objects.filter(owner=request.user)

    # filters
    if dtype:
        qs = qs.filter(document_type=dtype)
    if date_from:
        qs = qs.filter(uploaded_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(uploaded_at__date__lte=date_to)

    if q:
        query = SearchQuery(q, search_type="websearch", config="simple")

        filename_q = Q(file_name__icontains=q)

        qs = qs.filter(
            Q(search_vector=query) | filename_q
        ).annotate(
            rank=Coalesce(SearchRank(F("search_vector"), query), Value(0.0)),
            snippet=SearchHeadline(
                Coalesce("extracted_text", Value("")),
                query,
                config="simple",
                start_sel="",
                stop_sel="",
                max_words=35,
                min_words=15,
            ),
        ).order_by("-rank", "-uploaded_at")
    else:
        qs = qs.order_by("-uploaded_at")

    qs = qs.annotate(
        has_chat=Exists(
            Conversation.objects.filter(owner=request.user, document_id=OuterRef("pk"))
        )
    )

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    type_choices = ["invoice", "announcement", "policy", "proposal", "report", "research", "resume", "other"]

    return render(request, "documents/list.html", {
        "docs": page_obj.object_list,
        "dtype": dtype,
        "type_choices": type_choices,
        "page_obj": page_obj,

        "q": q,
        "date_from": date_from.isoformat() if date_from else "",
        "date_to": date_to.isoformat() if date_to else "",
    })

@login_required
@require_POST
def delete_document(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)

    page = (request.POST.get("page") or "").strip()
    dtype = (request.POST.get("dtype") or "").strip().lower()

    combined_qs = doc.combined_in.filter(owner=request.user).order_by("-created_at")
    if combined_qs.exists():
        combined_items = [
            {"id": x.id, "title": x.title}
            for x in combined_qs[:10]
        ]

        msg = "This document is used in a Combined Summary. Please delete the combined summary first."

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": False,
                    "code": "IN_COMBINED",
                    "error": msg,
                    "combined": combined_items,
                },
                status=409,
            )

        messages.warning(request, msg)
        return redirect("documents:list")

    file_field = doc.file
    file_name = doc.file_name

    try:
        if file_field:
            file_field.delete(save=False)
    except Exception:
        pass

    doc.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "deleted_id": pk, "deleted_name": file_name})

    messages.success(request, f"Deleted: {file_name}")

    if dtype or page:
        qs = {}
        if dtype:
            qs["type"] = dtype
        if page:
            qs["page"] = page
        return redirect(f"{reverse('documents:list')}?{urlencode(qs)}")

    return redirect("documents:list")

@login_required
def reprocess_document(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)
    process_document(doc)
    return redirect("documents:detail", pk=doc.pk)

@login_required
@require_GET
def search_documents_api(request):
    q = (request.GET.get("q") or "").strip()
    dtype = (request.GET.get("type") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    page = int(request.GET.get("page") or 1)

    qs = Document.objects.filter(owner=request.user)

    if dtype:
        qs = qs.filter(document_type=dtype)
    if date_from:
        qs = qs.filter(uploaded_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(uploaded_at__date__lte=date_to)

    if q:
        query = SearchQuery(q, search_type="websearch", config="simple")

        filename_q = Q(file_name__icontains=q)

        qs = qs.filter(
            Q(search_vector=query) | filename_q
        ).annotate(
            rank=Coalesce(SearchRank(F("search_vector"), query), Value(0.0)),
            snippet=SearchHeadline(
                Coalesce("extracted_text", Value("")),
                query,
                config="simple",
                start_sel="",
                stop_sel="",
                max_words=35,
                min_words=15,
            ),
        ).order_by("-rank", "-uploaded_at")
    else:
        qs = qs.order_by("-uploaded_at")

    # has_chat
    qs = qs.annotate(
        has_chat=Exists(
            Conversation.objects.filter(owner=request.user, document_id=OuterRef("pk"))
        )
    )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(page)

    items = []
    for d in page_obj.object_list:
        items.append({
            "id": d.id,
            "file_name": d.file_name,
            "document_type": d.document_type,
            "word_count": d.word_count,
            "char_count": d.char_count,
            "uploaded_at": timezone.localtime(d.uploaded_at).strftime("%-d %b %Y %H:%M"),
            "has_chat": bool(getattr(d, "has_chat", False)),
            "snippet": (getattr(d, "snippet", "") or "").strip(),
            "detail_url": reverse("documents:detail", kwargs={"pk": d.pk}),
            "chat_url": reverse("documents:chat_document", kwargs={"pk": d.pk}),
            "delete_url": reverse("documents:delete", kwargs={"pk": d.pk}),
        })

    return JsonResponse({
        "ok": True,
        "page": page_obj.number,
        "num_pages": page_obj.paginator.num_pages,
        "count": page_obj.paginator.count,
        "items": items,
    })


def _ascii_filename_fallback(name: str) -> str:
    """
    ทำชื่อไฟล์ให้เป็น ASCII ปลอดภัยสำหรับ header
    เช่น "AUCC2026____.pdf" ถ้าไทยเยอะ
    """
    name = (name or "").strip()
    # กันตัวอักษรอันตรายใน header
    name = name.replace('"', "").replace("\\", "").replace("\n", "").replace("\r", "")
    # แทน non-ascii เป็น _
    safe = re.sub(r"[^\x20-\x7E]", "_", name)  # ASCII printable
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "download"

def _content_disposition_inline(filename: str) -> str:
    ascii_name = _ascii_filename_fallback(filename)
    utf8_name = quote(filename, safe="")  # percent-encode UTF-8
    # RFC 5987
    return f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'

@login_required
def document_file(request, pk: int):
    doc = get_object_or_404(Document, pk=pk, owner=request.user)

    # doc.file.name = path แบบ relative ต่อ storage (ไม่มี "media/")
    key = doc.file.name
    # location = (getattr(settings, "AWS_LOCATION", "") or "").strip("/")

    # if location:
    #     key = f"{location}/{key.lstrip('/')}"

    s3 = boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)

    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": key,
            "ResponseContentDisposition": _content_disposition_inline(doc.file_name),
            "ResponseContentType": doc.mime_type or "application/octet-stream",
        },
        ExpiresIn=60,
    )
    return redirect(url)

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

    title, combined_text = build_combined_title_and_summary(docs, owner=request.user)

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
    items = CombinedSummary.objects.filter(owner=request.user).order_by("-created_at").annotate(
        has_chat=Exists(
            Conversation.objects.filter(owner=request.user, notebook_id=OuterRef("pk"))
        )
    )
    return render(request, "documents/combined_list.html", {"items": items})

@login_required
@require_POST
def delete_combined(request, pk: int):
    cs = get_object_or_404(CombinedSummary, pk=pk, owner=request.user)
    title = cs.title

    cs.delete()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "deleted_id": pk, "deleted_title": title})

    messages.success(request, f"Deleted combined summary: {title}")
    return redirect("documents:combined_list")

@login_required
@require_GET
def search_combined_api(request):
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "newest").strip()
    page = int(request.GET.get("page") or 1)

    qs = CombinedSummary.objects.filter(owner=request.user)

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(combined_summary__icontains=q)
        )

    if sort == "oldest":
        qs = qs.order_by("created_at")
    elif sort == "title":
        qs = qs.order_by("title", "-created_at")
    elif sort == "docs":
        qs = qs.order_by("-doc_count", "-created_at")
    elif sort == "words":
        qs = qs.order_by("-total_words", "-created_at")
    else:
        qs = qs.order_by("-created_at")

    qs = qs.annotate(
        has_chat=Exists(
            Conversation.objects.filter(owner=request.user, notebook_id=OuterRef("pk"))
        )
    )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(page)

    items = []
    for x in page_obj.object_list:

        items.append({
            "id": x.id,
            "title": x.title,
            "doc_count": x.doc_count,
            "total_words": x.total_words,
            "created_at": timezone.localtime(x.created_at).strftime("%-d %b %Y %H:%M"),
            "has_chat": bool(getattr(x, "has_chat", False)),
            "detail_url": reverse("documents:combined_detail", kwargs={"pk": x.pk}),
            "chat_url": reverse("documents:chat_notebook", kwargs={"pk": x.pk}),
            "delete_url": reverse("documents:combined_delete", kwargs={"pk": x.pk}),
        })

    return JsonResponse({
        "ok": True,
        "page": page_obj.number,
        "num_pages": page_obj.paginator.num_pages,
        "count": page_obj.paginator.count,
        "items": items,
    })

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

        try:
            assistant_text = answer_chat(conv, user_text) or "I couldn't generate a response."
        except LLMError as e:
            messages.error(request, str(e))
            return redirect("documents:chat_view", conv_id=conv.id)

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

    # if not check_daily_limit(request.user.id):
    #     return JsonResponse({"ok": False, "error": "Daily LLM limit reached. Please try again tomorrow."}, status=429)

    user_msg = Message.objects.create(conversation=conv, role="user", content=user_text)

    try:
        assistant_text = answer_chat(conv, user_text) or "I couldn't generate a response."
    except LLMError as e:
        user_msg.delete()
        msg = str(e)
        status = 429 if "Daily LLM limit" in msg else 502
        return JsonResponse({"ok": False, "error": msg}, status=status)

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
def chat_stream_api(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id, owner=request.user)

    user_text = (request.POST.get("message") or "").strip()
    rid = (request.POST.get("request_id") or "").strip()

    if not user_text:
        return JsonResponse({"ok": False, "error": "Empty message"}, status=400)
    if not rid:
        return JsonResponse({"ok": False, "error": "Missing request_id"}, status=400)

    cache.delete(f"chat_cancel:{conv.id}:{rid}")

    # if not check_daily_limit(request.user.id):
    #     return JsonResponse(
    #         {"ok": False, "error": "Daily LLM limit reached. Please try again tomorrow."},
    #         status=429,
    #     )

    user_msg = Message.objects.create(conversation=conv, role="user", content=user_text)

    def sse(event: str, data: dict):
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def gen():
        assistant_chunks = []
        try:
            def stopped():
                return cache.get(f"chat_cancel:{conv.id}:{rid}") is True

            for token in answer_chat_stream(conv, user_text, should_stop=stopped):
                if stopped():
                    user_msg.delete()
                    yield sse("canceled", {"ok": False})
                    return
                assistant_chunks.append(token)
                yield sse("token", {"t": token})

            assistant_text = "".join(assistant_chunks).strip() or "I couldn't generate a response."

            if cache.get(f"chat_cancel:{conv.id}:{rid}"):
                user_msg.delete()
                yield sse("canceled", {"ok": False})
                return

            Message.objects.create(conversation=conv, role="assistant", content=assistant_text)
            yield sse("done", {"ok": True, "created_at": timezone.now().strftime("%b. %d, %Y, %I:%M %p")})

        except LLMError as e:
            user_msg.delete()
            yield sse("error", {"ok": False, "error": str(e), "code": "LLM_ERROR"})
        except Exception as e:
            user_msg.delete()
            yield sse("error", {"ok": False, "error": str(e), "code": "SERVER_ERROR"})

    resp = StreamingHttpResponse(gen(), content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp

@login_required
@require_POST
def chat_cancel_api(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id, owner=request.user)
    rid = (request.POST.get("request_id") or "").strip()
    if not rid:
        return JsonResponse({"ok": False, "error": "Missing request_id"}, status=400)

    cache.set(f"chat_cancel:{conv.id}:{rid}", True, timeout=300)
    return JsonResponse({"ok": True})

def _next_midnight_iso():
    tz = timezone.get_current_timezone()
    now = timezone.localtime(timezone.now(), tz)
    tomorrow = (now + timedelta(days=1)).date()
    next_midnight = timezone.make_aware(datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0), tz)
    return next_midnight.isoformat()

@login_required
def usage_api(request):
    items = get_all_status(request.user.id)
    return JsonResponse({
        "ok": True,
        "reset_at": _next_midnight_iso(),
        "timezone": str(timezone.get_current_timezone()),
        "items": [
            {
                "purpose": s.purpose,
                "budget": s.budget,
                "spent": s.spent,
                "remaining": s.remaining,
                "ratio_remaining": s.ratio_remaining,
            }
            for s in items
        ]
    })