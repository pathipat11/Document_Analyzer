from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from django.conf import settings

@dataclass
class UploadLimits:
    max_files: int
    max_total_size: int
    max_file_size: int
    allowed_exts: set[str]

def get_limits() -> UploadLimits:
    return UploadLimits(
        max_files=getattr(settings, "MAX_FILES_PER_UPLOAD", 5),
        max_total_size=getattr(settings, "MAX_TOTAL_UPLOAD_SIZE", 20 * 1024 * 1024),
        max_file_size=getattr(settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024),
        allowed_exts=set(getattr(settings, "ALLOWED_EXTENSIONS", {"txt","csv","pdf","docx"})),
    )

def validate_files(files) -> None:
    limits = get_limits()

    if not files:
        raise ValueError("Please select at least one file.")

    if len(files) > limits.max_files:
        raise ValueError(f"Too many files. Max is {limits.max_files} files per upload.")

    total = sum(f.size for f in files)
    if total > limits.max_total_size:
        mb = limits.max_total_size // (1024*1024)
        raise ValueError(f"Total upload size too large. Max total is {mb}MB.")

    for f in files:
        if f.size > limits.max_file_size:
            mb = limits.max_file_size // (1024*1024)
            raise ValueError(f"File '{f.name}' is too large. Max per file is {mb}MB.")
        ext = Path(f.name).suffix.lower().lstrip(".")
        if ext not in limits.allowed_exts:
            raise ValueError(f"Unsupported file type: .{ext} for '{f.name}'.")
