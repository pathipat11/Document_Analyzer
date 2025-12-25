from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("health/", views.health, name="health"),

    path("", views.document_list, name="list"),
    path("upload/", views.upload_document, name="upload"),
    path("documents/<int:pk>/", views.document_detail, name="detail"),
    path("documents/<int:pk>/reprocess/", views.reprocess_document, name="reprocess"),

    path("export/csv/", views.export_documents_csv, name="export_csv"),
]
