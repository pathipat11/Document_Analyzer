from django.core.management.base import BaseCommand
from documents.models import Document
from documents.services.search.search_index import update_document_search_vector

class Command(BaseCommand):
    help = "Rebuild search_vector for all documents"

    def add_arguments(self, parser):
        parser.add_argument("--owner-id", type=int, default=None)

    def handle(self, *args, **opts):
        qs = Document.objects.all().order_by("id")
        owner_id = opts.get("owner_id")
        if owner_id:
            qs = qs.filter(owner_id=owner_id)

        total = qs.count()
        self.stdout.write(f"Rebuilding search_vector for {total} documents...")

        for i, d in enumerate(qs.iterator(chunk_size=200), start=1):
            update_document_search_vector(d.id)
            if i % 200 == 0:
                self.stdout.write(f"  {i}/{total}")

        self.stdout.write("Done.")
