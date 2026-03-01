# Document Analyzer

`Document Analyzer` is a Django web application for uploading documents, extracting text, generating AI summaries, classifying document types, searching content with PostgreSQL full-text search, and chatting against a single document or a multi-document notebook.

The current codebase is organized around a service layer under `documents/services/` and supports both local LLM inference with Ollama and cloud inference through AWS Bedrock.

## Features

### Document management

- User registration, login, password reset, profile edit, deactivate account, and delete account
- Per-user document isolation on all document, notebook, and chat queries
- Multi-file upload with validation for:
  - Allowed extensions: `.txt`, `.csv`, `.pdf`, `.docx`
  - Maximum file size per file
  - Maximum total upload size per request
  - Maximum files per upload
- Reprocess an uploaded document
- Delete documents safely, including protection when a file is already linked to a combined summary
- CSV export for a user document list

### Processing pipeline

Each uploaded file is processed synchronously:

1. Save file through Django storage
2. Extract raw text by file type
3. Sanitize text
4. Compute word count and character count
5. Chunk extracted text for retrieval
6. Generate summary
7. Classify document type
8. Build PostgreSQL search vector
9. Move the file into a type-based storage path

Supported document type labels:

- `invoice`
- `announcement`
- `policy`
- `proposal`
- `report`
- `research`
- `resume`
- `other`

### Search and browsing

- PostgreSQL full-text search on file name, summary, and extracted text
- Ranked search results with snippets
- Filters by document type and upload date
- Paginated document list
- Separate combined-summary list with query and sorting options
- Search index rebuild command: `python manage.py rebuild_search`

### Combined summaries

- Auto-create a notebook when uploading multiple files
- Manually combine selected documents from the document list
- AI-generated notebook title
- Cross-document summary generated from per-document summaries
- Notebook detail page with linked source documents
- Separate notebook chat entry point

### Chat

- Chat tied to a single document or a combined notebook
- Context built from document summary plus retrieved chunks
- Streaming chat via Server-Sent Events
- Cancel in-progress generation
- Reset chat history
- Regenerate assistant responses
- Citation-style chunk references in grounded answers such as `[D12-C3]`
- Language-aware responses for Thai and English

### Quotas and usage

- Daily LLM call guardrail
- Separate token budgets for `chat` and `upload`
- Remaining budget API for UI indicators
- Token usage logging in `LLMCallLog`

### Storage and delivery

- Uploaded files stored through Django `FileField`
- Current settings use `django-storages` S3 storage for media
- Secure document access through presigned S3 URLs
- Inline preview headers for supported files

## Architecture

```text
documents/
├── models.py
├── views.py
├── urls.py
├── management/commands/
└── services/
    ├── analysis/
    ├── chat/
    ├── llm/
    ├── pipeline/
    ├── search/
    ├── storage/
    └── upload/
```

Design choices in the current implementation:

- Thin Django views
- Service-based processing and chat orchestration
- Provider abstraction for LLM calls
- PostgreSQL-native search instead of an external search engine
- Cache-backed token ledger for daily usage tracking
- Synchronous processing on upload

## Stack

- Python 3
- Django 6
- PostgreSQL
- Tailwind CSS 4
- Ollama
- AWS Bedrock
- Amazon S3 via `django-storages`
- Server-Sent Events for chat streaming

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
npm install
```

Note: the codebase also imports `boto3`, `botocore`, and `django-storages`. If they are not already available in your environment, install them as well.

### 2. Create environment variables

Example `.env`:

```env
DJANGO_SECRET_KEY=dev-secret-key
DJANGO_DEBUG=1

DB_NAME=document_analyzer
DB_USER=postgres
DB_PASSWORD=root
DB_HOST=127.0.0.1
DB_PORT=5432

MAX_UPLOAD_SIZE=5242880
MAX_FILES_PER_UPLOAD=5
MAX_TOTAL_UPLOAD_SIZE=20971520
ALLOWED_EXTENSIONS=txt,csv,pdf,docx

ENABLE_LLM=1
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

AWS_REGION=us-east-1
BEDROCK_INFERENCE_PROFILE_ARN=
BEDROCK_MAX_TOKENS=800
BEDROCK_TEMPERATURE=0.2

LLM_DAILY_CALL_LIMIT=0
LLM_TOKENS_CHAT=0
LLM_TOKENS_UPLOAD=0

AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=ap-southeast-1

EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
SITE_DOMAIN=127.0.0.1:8000
SITE_PROTOCOL=http
```

### 3. Prepare the database

```bash
python manage.py migrate
```

### 4. Build frontend assets

```bash
npm run build:css
```

For active UI work:

```bash
npm run watch:css
```

### 5. Run the app

```bash
python manage.py runserver
```

## Main URLs

- `/` landing page
- `/app/` document list
- `/upload/` upload page
- `/combined/` combined summaries
- `/accounts/login/` login
- `/admin/` Django admin
- `/health/` health check

## Key Models

- `Document`: uploaded file, extracted text, summary, classification, metadata, search vector
- `CombinedSummary`: notebook built from multiple documents
- `Conversation`: chat target bound to exactly one document or one notebook
- `Message`: chat history with active/inactive and edit lineage fields
- `LLMCallLog`: provider, purpose, latency, token usage, success or error
- `DocumentChunk`: retrieval chunks for grounded chat

## LLM Providers

The application supports two providers through `documents/services/llm/client.py`:

- `ollama`
- `bedrock`

Switch provider with:

```env
LLM_PROVIDER=ollama
```

or

```env
LLM_PROVIDER=bedrock
BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:region:account:inference-profile/...
```

## Notes and current limitations

- PDF support is text extraction only. There is no OCR pipeline.
- Upload processing is synchronous, so large batches will block the request until processing finishes.
- PostgreSQL is required because the project uses `django.contrib.postgres` search features.
- Token budgets are cache-backed. If you want shared budget state across multiple app instances, configure a shared cache backend such as Redis.
- The default `settings.py` media storage is S3-backed. For purely local file storage, you will need to adjust the storage configuration.
