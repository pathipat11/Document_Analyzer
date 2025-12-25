from django import forms
from django.conf import settings
from pathlib import Path

class DocumentUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data["file"]

        # 1) size limit
        max_size = getattr(settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024)
        if f.size > max_size:
            raise forms.ValidationError(f"File too large. Max size is {max_size // (1024*1024)}MB.")

        # 2) extension allowlist
        allowed = getattr(settings, "ALLOWED_EXTENSIONS", {"txt", "csv", "pdf", "docx"})
        ext = Path(f.name).suffix.lower().lstrip(".")
        if ext not in allowed:
            raise forms.ValidationError(f"Unsupported file type: .{ext}. Allowed: {', '.join(sorted(allowed))}")

        return f
