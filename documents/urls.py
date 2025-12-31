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

    path("combined/", views.combined_list, name="combined_list"),
    path("combined/create/", views.create_combined_summary, name="combined_create"),
    path("combined/<int:pk>/", views.combined_detail, name="combined_detail"),
    
    path("chat/document/<int:pk>/", views.chat_document, name="chat_document"),
    path("chat/notebook/<int:pk>/", views.chat_notebook, name="chat_notebook"),
    path("chat/<int:conv_id>/", views.chat_view, name="chat_view"),
    path("chat/<int:conv_id>/api/", views.chat_api, name="chat_api"),
]
