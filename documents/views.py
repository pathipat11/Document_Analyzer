from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

from .forms import DocumentUploadForm
from .services.processor import process_document
from .models import Document

def health(request):
    return JsonResponse({"status": "ok"})

def upload_document(request):
    if request.method == "POST":
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["file"]

            ext = Path(f.name).suffix.lower().lstrip(".")
            # content_type อาจว่างสำหรับบางไฟล์/บาง browser ได้
            mime = getattr(f, "content_type", "") or ""

            doc = Document.objects.create(
                file=f,                 # Django จะ save ลง MEDIA_ROOT/upload_to
                file_name=f.name,
                file_ext=ext,
                mime_type=mime,
                uploaded_at=timezone.now(),  # optional (auto_now_add ก็ทำอยู่แล้ว)
            )

            process_document(doc)
            return redirect("documents:detail", pk=doc.pk)
    else:
        form = DocumentUploadForm()

    return render(request, "documents/upload.html", {"form": form})

def document_detail(request, pk: int):
    doc = get_object_or_404(Document, pk=pk)
    return render(request, "documents/detail.html", {"doc": doc})

def document_list(request):
    docs = Document.objects.order_by("-uploaded_at")
    return render(request, "documents/list.html", {"docs": docs})

def reprocess_document(request, pk: int):
    doc = get_object_or_404(Document, pk=pk)
    process_document(doc)
    return redirect("documents:detail", pk=doc.pk)