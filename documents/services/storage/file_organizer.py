import os
from django.core.files.storage import default_storage

SAFE_TYPES = {"invoice","announcement","policy","proposal","report","research","resume","other"}

def _safe_type(dtype: str) -> str:
    t = (dtype or "other").strip().lower()
    return t if t in SAFE_TYPES else "other"

def move_document_file_to_type_folder(doc):
    if not doc.file or not doc.file.name:
        return

    dtype = _safe_type(getattr(doc, "document_type", "other"))
    owner_id = getattr(doc, "owner_id", None) or "unknown"

    old_name = doc.file.name  # เช่น incoming/user_4/2026/01/a.pdf
    filename = os.path.basename(old_name)

    new_name = f"{dtype}/user_{owner_id}/{filename}"  # เช่น research/user_4/a.pdf

    if old_name == new_name:
        return

    # ถ้าปลายทางซ้ำ เติม suffix
    if default_storage.exists(new_name):
        base, ext = os.path.splitext(filename)
        i = 2
        while default_storage.exists(f"{dtype}/user_{owner_id}/{base}_{i}{ext}"):
            i += 1
        new_name = f"{dtype}/user_{owner_id}/{base}_{i}{ext}"

    # copy แบบ stream
    with default_storage.open(old_name, "rb") as f:
        default_storage.save(new_name, f)

    # ลบไฟล์เก่า
    try:
        default_storage.delete(old_name)
    except Exception:
        pass

    # update DB
    doc.file.name = new_name
    doc.save(update_fields=["file"])
