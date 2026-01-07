import os
from django.conf import settings
from django.core.files.storage import default_storage

SAFE_TYPES = {"invoice","announcement","policy","proposal","report","research","resume","other"}

def _safe_type(dtype: str) -> str:
    t = (dtype or "other").strip().lower()
    return t if t in SAFE_TYPES else "other"

def move_document_file_to_type_folder(doc):
    """
    Move file from documents/_incoming/... to documents/<type>/user_<id>/...
    and update doc.file.name
    """
    if not doc.file:
        return
    if not doc.file.name:
        return

    dtype = _safe_type(getattr(doc, "document_type", "other"))
    owner_id = getattr(doc, "owner_id", None) or "unknown"

    old_name = doc.file.name  # path relative to MEDIA_ROOT
    filename = os.path.basename(old_name)

    new_name = f"documents/{dtype}/user_{owner_id}/{filename}"

    # ถ้าปลายทางซ้ำ ให้เติม suffix กันชน
    if default_storage.exists(new_name):
        base, ext = os.path.splitext(filename)
        i = 2
        while default_storage.exists(f"documents/{dtype}/user_{owner_id}/{base}_{i}{ext}"):
            i += 1
        new_name = f"documents/{dtype}/user_{owner_id}/{base}_{i}{ext}"

    # read -> save -> delete (works with default_storage)
    with default_storage.open(old_name, "rb") as f:
        default_storage.save(new_name, f)

    # ลบไฟล์เก่า
    try:
        default_storage.delete(old_name)
    except Exception:
        pass

    # อัปเดต path ใน DB
    doc.file.name = new_name
    doc.save(update_fields=["file"])