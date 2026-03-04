# Document Analyzer

`Document Analyzer` is a Django application for ingesting documents, extracting text, analyzing content with an LLM, and turning the result into something users can search, summarize, and chat with.

It is not just an upload screen with an AI summary. The project covers the full document workflow:

1. accept user uploads
2. validate and store files
3. extract and normalize text
4. generate metadata and AI analysis
5. index documents for search
6. support grounded chat against one document or many documents

## What the system does

- Upload one or many files in a single request
- Support `.txt`, `.csv`, `.pdf`, and `.docx`
- Extract text and store it in PostgreSQL
- Generate document summaries with an LLM
- Classify each document into a fixed document type
- Search documents with PostgreSQL full-text search
- Create notebook-style summaries across multiple documents
- Chat with a single document or a combined notebook
- Track usage and enforce LLM quotas
- Serve document files securely through presigned S3 URLs

## System at a glance

From a user point of view, the main workflow looks like this:

```text
Upload file(s)
  -> Validate
  -> Store file
  -> Extract text
  -> Build metadata
  -> Summarize
  -> Classify
  -> Index for search
  -> Search / Combine / Chat
```

From a codebase point of view, the project is structured around a service layer:

```text
documents/
├── models.py
├── views.py
├── urls.py
├── management/commands/
└── services/
    ├── upload/
    ├── pipeline/
    ├── analysis/
    ├── search/
    ├── chat/
    ├── llm/
    └── storage/
```

The main architectural choice is simple: keep views thin, keep orchestration in services, and keep provider-specific logic behind a shared LLM client.

## Core concepts

### Documents

A `Document` is the central object in the system. It stores:

- the uploaded file
- file metadata such as extension and MIME type
- extracted text
- summary
- document type
- word and character counts
- processing status
- PostgreSQL search vector

Each document belongs to a user, so document access is isolated per account.

### Chunks

During processing, extracted text is split into smaller `DocumentChunk` records. These chunks are used later for retrieval during chat.

The reason is practical: chat does not need the full raw document every time. It only needs the most relevant parts.

### Combined summaries

A `CombinedSummary` is a notebook-style object built from multiple documents. It stores:

- a generated or user-provided title
- a higher-level combined summary
- the related documents
- aggregate metadata such as document count and total words

This gives users a way to work at the collection level instead of only at the single-document level.

### Conversations

A `Conversation` is a chat session tied to exactly one target:

- one `Document`, or
- one `CombinedSummary`

That constraint is enforced in the model, which keeps chat context explicit and avoids ambiguous conversations.

## How upload and processing work

The upload flow starts at `/upload/`.

Before a file is processed, the app validates:

- that the request contains at least one file
- that the number of files does not exceed the configured maximum
- that each file stays under the per-file size limit
- that the total request size stays under the total upload limit
- that the file extension is allowed

Once validation passes, the system creates a `Document` row and processes it synchronously.

The main processing pipeline lives in `documents/services/pipeline/processor.py`.

For each file, the app:

1. reads the file from storage
2. extracts text based on file type
3. sanitizes the extracted text
4. computes `word_count` and `char_count`
5. creates retrieval chunks
6. generates a summary through the LLM
7. generates a document type through the LLM
8. updates the PostgreSQL search index fields
9. moves the stored file into a type-based path

Document progress is tracked through `Document.status`, including states such as `queued`, `processing`, `done`, and `error`.

## How search works

Search is implemented directly with PostgreSQL rather than a separate search engine.

After processing, each document gets a `search_vector` built from:

- `file_name`
- `summary`
- `extracted_text`

When a user searches, the app uses PostgreSQL features such as:

- `SearchQuery`
- `SearchRank`
- `SearchHeadline`

This allows the UI to provide:

- keyword search across document names and content
- ranked results
- matching snippets
- filtering by document type
- filtering by upload date

If search vectors need to be rebuilt:

```bash
python manage.py rebuild_search
```

## How combined summaries work

Combined summaries can be created in two ways:

1. upload multiple files and enable auto-combine
2. select multiple existing documents and combine them manually

The strategy is intentionally lightweight and token-aware:

```text
Per-document summary
  -> merge summaries
  -> generate notebook title
  -> generate combined summary
```

This is effectively a simple map-reduce pattern. Instead of sending the full raw content of every document to the model again, the system reduces across document summaries first. That keeps prompt size smaller and makes multi-document summarization more predictable.

## How chat works

Chat is designed to be grounded in document content rather than operating as a generic assistant with no context.

### Chat against a single document

For document chat, the app builds context from:

- the document summary
- the highest-scoring chunks related to the user question

Only the relevant context is included in the final prompt.

### Chat against a combined notebook

For notebook chat, the app builds context from:

- the notebook title
- the combined summary
- per-document summaries
- high-scoring chunks pulled from the linked documents

This allows the assistant to answer both broad and targeted questions across multiple files.

### Retrieval strategy

The retrieval layer in this project is heuristic, not embedding-based.

It works by:

- tokenizing the user question
- removing Thai and English stopwords
- comparing term overlap between the question and each chunk
- rewarding chunks that match more useful terms
- applying a small penalty to overly long chunks

The result is a simple RAG-like flow without adding a vector database.

## Chat features

The chat layer supports more than plain request-response messaging.

Current capabilities include:

- normal chat requests
- real-time streaming through Server-Sent Events
- canceling an in-progress generation
- resetting a conversation
- regenerating an answer from an earlier user message
- branching the conversation after a user edit

The `Message` model stores `is_active`, `parent_message`, and `edited_from`, which allows the app to keep a lightweight editable conversation tree.

## LLM providers and quotas

All model access goes through `documents/services/llm/client.py`.

The code currently supports:

- `ollama`
- `bedrock`

Higher-level services call shared functions such as:

- `generate_text()`
- `generate_text_stream()`

This keeps provider-specific behavior out of most business logic.

The system also applies two guardrails:

- daily LLM call limits
- token budgets by feature

Budgets are tracked separately for:

- `chat`
- `upload`

Usage is stored through the token ledger and exposed to the frontend through `usage_api`.

## File storage and delivery

Uploaded files are stored through Django `FileField`.

In the current configuration, media storage uses S3 through `django-storages`. Files are not exposed directly. When a user wants to open a document, the app:

```text
checks document ownership
  -> creates a short-lived presigned URL
  -> redirects the user to that URL
```

This keeps uploaded files private while still allowing secure preview and download.

## Main user-facing routes

- `/`
  landing page

- `/app/`
  document list with search, filters, pagination, and actions

- `/upload/`
  upload page

- `/documents/<id>/`
  single-document detail page

- `/combined/`
  list of combined summaries

- `/combined/<id>/`
  combined summary detail page

- `/chat/<conv_id>/`
  chat page

- `/accounts/*`
  authentication, profile, and password reset flows

- `/health/`
  health check endpoint

## Supported document types

The classifier assigns one of these labels:

- `invoice`
- `announcement`
- `policy`
- `proposal`
- `report`
- `research`
- `resume`
- `other`

## Tech stack

- Python 3
- Django 6
- PostgreSQL
- Tailwind CSS 4
- Ollama
- AWS Bedrock
- Amazon S3 via `django-storages`
- Server-Sent Events

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
npm install
```

Note: the current code also imports `boto3`, `botocore`, and `django-storages`. If those packages are not already present in your environment, install them as well.

### 2. Create `.env`

Example baseline configuration:

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

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Build CSS

```bash
npm run build:css
```

For active frontend work:

```bash
npm run watch:css
```

### 5. Start the server

```bash
python manage.py runserver
```

## Current limitations

- PDF support is text extraction only. There is no OCR pipeline.
- Upload processing is synchronous, so large batches block the request until processing finishes.
- Search depends on PostgreSQL-specific features from `django.contrib.postgres`.
- Token usage is cache-backed; for multi-instance deployments, a shared cache such as Redis is a better fit.
- The default media configuration is S3-backed. If you want purely local file storage, you need to adjust the storage settings.
