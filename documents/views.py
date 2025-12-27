import csv
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q

from .services.upload_validation import validate_files, get_limits
from .services.processor import process_document
from .models import Document

def health(request):
    return JsonResponse({"status": "ok"})

@login_required
def upload_document(request):
    limits = get_limits()

    if request.method == "POST":
        files = request.FILES.getlist("files")

        try:
            validate_files(files)
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, "documents/upload.html", {"limits": limits})

        created = []
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

        messages.success(request, f"Uploaded and processed {len(created)} file(s).")
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