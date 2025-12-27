# Document Intake & Analysis System (Local Prototype)

## Overview

Document Intake & Analysis System is a local-first Django web application designed to ingest, analyze, and summarize documents using a local Large Language Model (LLM) via Ollama. The system supports single-document analysis as well as multi-document *notebook-style* summaries, allowing users to upload multiple files and generate consolidated insights.

The project is built as a **prototype** to explore document processing workflows, LLM integration, and system design that can be extended into a more production-ready solution.

---

## Key Features

### Document Management

* User authentication (login/register)
* Upload one or multiple documents at once
* Supported file types: `.txt`, `.csv`, `.pdf`, `.docx`
* File validation:

  * Maximum files per upload
  * Maximum total upload size
  * Maximum size per file
* Documents are private to each user

### Text Processing & Analysis

* Text extraction per file type
* Automatic word count and character count
* Document type classification (e.g. invoice, report, research, proposal, resume, etc.)
* Short document summary (2–3 sentences)
* Summary language automatically matches the source document language (Thai / English)

### Notebook-Style Combined Summary

* Upload multiple files and automatically create a combined summary (optional toggle)
* Manually select existing documents to create a combined summary
* Combined summary uses a map-reduce approach:

  * Per-document summaries
  * Consolidated summary across documents
* AI-generated notebook title based on document content
* View combined summaries separately from individual documents

### User Interface

* Clean UI built with Tailwind CSS
* Light / Dark theme toggle (saved in browser)
* Toast notifications for actions (upload, logout, errors)
* Document list with filters and selection

### Data Export & Admin

* Export document metadata as CSV
* Django Admin customization for document inspection

---

## How to Use

### 1. Login / Register

* Create a user account or log in with an existing account
* Each user can only see and manage their own documents and notebooks

### 2. Upload Documents

* Navigate to **Upload** from the top navigation bar
* Select one or multiple files (`.txt`, `.csv`, `.pdf`, `.docx`)
* Review upload limits shown on the page (file count and size)
* Optionally enable **Auto-combine and summarize** to create a notebook immediately when uploading multiple files
* Click **Upload** and wait for processing to complete

### 3. View Documents

* After upload, you will be redirected to:

  * **Document Detail** (single file upload), or
  * **Document List** (multiple files)
* Each document shows:

  * Extracted metadata (word count, character count)
  * Detected document type
  * Short AI-generated summary

### 4. Create a Combined (Notebook) Summary

There are two ways to create a notebook-style summary:

**Option A: Auto-combine during upload**

* Upload multiple files
* Enable the auto-combine toggle
* The system will automatically:

  * Generate summaries per document
  * Create a notebook title
  * Produce a consolidated summary

**Option B: Manual combine from document list**

* Go to **Documents**
* Select at least two documents using the checkboxes
* Click **Combine & Summarize**
* A new notebook summary will be created

### 5. View Combined Summaries

* Navigate to **Combined** from the top menu
* Each combined summary displays:

  * AI-generated notebook title
  * Consolidated summary across documents
  * List of source documents used

### 6. Export Data

* From the document list, use **Export CSV** to download document metadata
* Filters applied in the UI will be reflected in the exported file

---

## Architecture

### Application Structure

* `documents/views.py`

  * HTTP request handling
  * Authentication and access control
  * Upload, list, detail, and combine workflows

* `documents/models.py`

  * `Document`: individual uploaded document
  * `CombinedSummary`: notebook-style summary created from multiple documents

* `documents/services/`

  * `text_extractor.py`: extract text from different file formats
  * `processor.py`: orchestrates extraction, analysis, and LLM calls
  * `llm_client.py`: wrapper for local Ollama model
  * `summarizer.py`: per-document summarization
  * `classifier.py`: document type classification
  * `combined_summarizer.py`: multi-document map-reduce summarization
  * `title_generator.py`: AI-generated notebook titles
  * `lang_detect.py`: simple language detection (Thai / English)

This separation keeps views thin and business logic reusable and testable.

---

## Processing Flow

### Single Document

Upload → Validate → Save File → Extract Text → Compute Metadata → LLM Summary & Type → Save → Detail View

### Multiple Documents (Notebook Style)

Upload Multiple Files → Validate → Save Files → Extract & Summarize Each → Generate Notebook Title → Create Combined Summary → Notebook Detail View

### Mermaid Flow Diagram

```mermaid
flowchart TD
  A[User uploads document(s)] --> B{Validate}
  B -->|Fail| B1[Show error toast]
  B -->|Pass| C[Save file(s) to media/]

  C --> D[Create Document row(s) in DB
(owner, metadata)]
  D --> E[Extract text
(txt/csv/pdf/docx)]
  E --> F[Compute word_count & char_count]

  F --> G{LLM enabled?}
  G -->|No| H[Save extracted_text + counts]
  G -->|Yes| I[Generate summary
(Thai/English auto)]
  I --> J[Classify document_type]
  J --> H[Save extracted_text + counts + summary + type]

  H --> K{Multiple files & auto-combine?}
  K -->|No| L{Single file?}
  L -->|Yes| M[Redirect: Document detail]
  L -->|No| N[Redirect: Document list]

  K -->|Yes| O[Map: use per-document summaries]
  O --> P[AI generate notebook title]
  P --> Q[Reduce: consolidated summary
(4-6 bullets)]
  Q --> R[Create CombinedSummary + link documents]
  R --> S[Redirect: Combined summary detail]
```

---

## Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL (local)
* **LLM:** Ollama (local model, e.g. `llama3`)
* **Frontend:** Django Templates + Tailwind CSS
* **Auth:** Django Authentication System

---

## Local Setup

### Prerequisites

* Python 3.11+ (recommended)
* PostgreSQL (local)
* Ollama installed and running

### 1) Clone the project

```bash
git clone <your-repo-url>
cd document_analyzer
```

### 2) Create & activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
# .venv/Scripts/Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Configure environment variables

Create a `.env` file in the project root (same level as `manage.py`). Example:

```dotenv
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=1

DB_NAME=document_analyzer
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432

MAX_UPLOAD_SIZE=5242880
ALLOWED_EXTENSIONS=txt,csv,pdf,docx

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3
ENABLE_LLM=1
```

### 5) Create the database (PostgreSQL)

Create a local database named `document_analyzer` (adjust to match `.env`).

```bash
createdb document_analyzer
```

If you prefer psql:

```bash
psql -U postgres -c "CREATE DATABASE document_analyzer;"
```

### 6) Run migrations

```bash
python manage.py migrate
```

### 7) Create an admin user (optional)

```bash
python manage.py createsuperuser
```

### 8) Ensure Ollama is running and pull a model

Start Ollama, then pull the model configured in `.env`:

```bash
ollama pull llama3
```

(If you change models, update `OLLAMA_MODEL` accordingly.)

### 9) Run the development server

```bash
python manage.py runserver
```

Open the app:

* [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

Admin (optional):

* [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

### Troubleshooting

* **Database connection error**: verify `DB_*` in `.env`, confirm PostgreSQL is running, and the database exists.
* **Ollama not responding**: confirm Ollama is running at `OLLAMA_HOST` and the model is pulled.
* **PDF produces empty text**: the PDF may be scanned/image-based; OCR is not included in this prototype.
* **Large uploads feel slow**: processing is synchronous in this prototype; consider background jobs as a next step.

---

## Limitations

* PDF extraction supports text-based PDFs only (no OCR for scanned documents)
* LLM output quality depends on the local model and hardware
* Processing is synchronous; large uploads may take time
* Designed as a prototype, not optimized for high concurrency

---

## Future Improvements

* Background processing (Celery / task queue)
* Chat-based Q&A over documents and notebooks
* Embedding-based retrieval for large document sets
* Export combined summaries as Markdown or text

---