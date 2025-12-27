from django import forms
from django.conf import settings
from pathlib import Path

class MultiDocumentUploadForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={"multiple": True}))

    def clean_files(self):
        files = self.files.getlist("files") if hasattr(self, "files") else None
        # NOTE: clean_files จะถูกเรียกหลัง binding; เราจะใช้ request.FILES ใน view ก็ได้
        # แต่เพื่อให้ form ทำงานเองได้: ใช้ self.files (Django) ใน view ต้องส่ง request.FILES เข้ามา
        return files
