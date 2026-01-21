from django.contrib.postgres.search import SearchVector
from django.db.models import F, Value, TextField
from django.db.models.functions import Cast, Coalesce

from documents.models import Document

def update_document_search_vector(doc_id: int):
    Document.objects.filter(id=doc_id).update(
        search_vector=(
            SearchVector(Cast("file_name", TextField()), weight="A", config="simple")
            + SearchVector(Cast("summary", TextField()), weight="A", config="simple")
            + SearchVector(Cast("extracted_text", TextField()), weight="B", config="simple")
        )
    )