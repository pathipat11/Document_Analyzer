from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("health/", views.health, name="health"),

    path("", views.home, name="home"),
    
    path("app", views.document_list, name="list"),
    
    path("upload/", views.upload_document, name="upload"),
    path("documents/<int:pk>/", views.document_detail, name="detail"),
    path("documents/<int:pk>/delete/", views.delete_document, name="delete"),
    path("documents/<int:pk>/reprocess/", views.reprocess_document, name="reprocess"),
    path("documents/<int:pk>/file/", views.document_file, name="file"),

    path("api/search/", views.search_documents_api, name="search_api"),
    path("api/combined/search/", views.search_combined_api, name="combined_search_api"),

    path("export/csv/", views.export_documents_csv, name="export_csv"),

    path("combined/", views.combined_list, name="combined_list"),
    path("combined/create/", views.create_combined_summary, name="combined_create"),
    path("combined/<int:pk>/", views.combined_detail, name="combined_detail"),
    path("combined/<int:pk>/delete/", views.delete_combined, name="combined_delete"),
    
    
    path("chat/document/<int:pk>/", views.chat_document, name="chat_document"),
    path("chat/notebook/<int:pk>/", views.chat_notebook, name="chat_notebook"),
    path("chat/<int:conv_id>/", views.chat_view, name="chat_view"),
    path("chat/<int:conv_id>/api/", views.chat_api, name="chat_api"),
    path("chat/<int:conv_id>/stream/", views.chat_stream_api, name="chat_stream_api"),
    path("chat/<int:conv_id>/cancel/", views.chat_cancel_api, name="chat_cancel_api"),

    path("api/usage/", views.usage_api, name="usage_api"),
]
