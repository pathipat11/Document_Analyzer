# Document Intake & Analysis System

## Overview

**Document Intake & Analysis System** is a Django-based document processing and analysis platform designed to ingest, analyze, summarize, and interact with documents using **Large Language Models (LLMs)**. The system supports both **local-first development** (via Ollama) and **cloud-based inference** (via **AWS Bedrock – Claude 3.5**), making it suitable as a learning prototype that can be gradually evolved toward a production-ready architecture.

The application focuses on **end-to-end document workflows**:

* Secure document upload and storage
* Text extraction and metadata analysis
* AI-powered summarization and classification
* Notebook-style multi-document analysis
* Real-time, cancelable chat with streaming responses

The project emphasizes **clean service separation**, **bounded context**, and **LLM-safe patterns** such as rate limiting, streaming, and cancellation.

---

## Key Features

### 1. Document Management

* User authentication (Django auth)
* Upload **single or multiple documents**
* Supported formats:

  * `.txt`, `.csv`, `.pdf` (text-based), `.docx`
* Upload validation:

  * Maximum number of files per request
  * Maximum total upload size
  * Maximum size per file
* Documents are **private per user** (ownership enforced at query level)
* Safe delete:

  * Removes file from storage
  * Deletes DB record
  * Preserves pagination + filters after deletion

---

### 2. Text Extraction & Metadata Analysis

For each uploaded document:

* Text extraction by file type
* Automatic metadata calculation:

  * Word count
  * Character count
* Extracted text is stored for downstream processing

> PDFs are supported only if they contain extractable text (OCR is intentionally excluded in this prototype).

---

### 3. AI-Powered Analysis

#### 3.1 Document Summarization

* Short, concise summary (2–3 sentences)
* Summary language automatically matches the document language:

  * Thai / English
* Designed to be fast and cost-aware

#### 3.2 Document Classification

* Automatic classification into predefined types:

  * `invoice`, `announcement`, `policy`, `proposal`, `report`, `research`, `resume`, `other`
* Strict single-label output enforced at prompt level
* Used for filtering and organization in the UI

---

### 4. Notebook-Style Combined Summary (Map–Reduce)

The system supports **multi-document analysis** via a *notebook* abstraction.

#### Creation Options

* **Auto-combine on upload** (when uploading multiple files)
* **Manual combine** from the document list

#### Processing Strategy

* **Map step**: generate summaries for each document
* **Reduce step**:

  * Generate a consolidated summary across all documents
  * Produce an AI-generated notebook title

Each notebook contains:

* Title
* Combined summary
* Linked source documents
* Aggregate metadata (document count, total words)

---

### 5. Chat Q&A (Document & Notebook)

Users can chat with:

* A **single document**, or
* A **notebook (combined summary)**

#### Core Capabilities

* Context-aware Q&A using extracted text and summaries
* Retrieval-augmented prompting for documents (top relevant chunks)
* Conversation history included (bounded by recent turns)

#### Streaming + Cancel (ChatGPT-like UX)

* **Server-Sent Events (SSE)** token streaming
* Tokens appear in real time
* Single button UX:

  * `Send` → `Cancel`
* Dual cancellation mechanism:

  * Client-side abort (`AbortController`)
  * Server-side cancel flag (prevents saving partial responses)

This ensures:

* Lower perceived latency
* No wasted tokens
* No partial assistant messages saved

---

### 6. LLM Architecture (Local + Cloud)

The system abstracts LLM usage behind a dedicated service layer.

#### Supported Providers

* **Ollama (local-first)**

  * Used for development and experimentation
* **AWS Bedrock (Claude 3.5 Haiku via Inference Profile ARN)**

  * Production-style managed inference
  * Supports streaming responses

Switching providers is controlled via environment variables:

```env
LLM_PROVIDER=bedrock  # or ollama
```

#### Unified LLM Client

* `generate_text(...)` – synchronous responses
* `generate_text_stream(...)` – streaming responses
* Centralized logging via `LLMCallLog`
* Consistent interface across providers

---

### 7. Guardrails & Cost Control

To prevent runaway usage and control costs:

* **Daily per-user LLM quota**

  * Enforced at service level
  * Checked before each request
* Unified guardrail logic shared by:

  * Chat
  * Summarization
  * Classification

When the limit is reached:

* API returns `429`
* UI displays a clear, user-friendly message

---

### 8. Storage Abstraction (Local → Cloud Ready)

* Uses Django’s storage abstraction (`FileField` + storage backend)
* Designed to migrate from:

  * Local filesystem (`MEDIA_ROOT`)
  * → **Amazon S3** (planned)

Key design choices:

* File access via storage streams (not `.path`)
* Compatible with private S3 buckets
* Ready for pre-signed download URLs

---

### 9. User Interface & UX

* Built with **Django Templates + Tailwind CSS**
* Light / Dark mode toggle (persisted in browser)
* Responsive layout
* Toast notifications for:

  * Upload success/failure
  * Delete actions
  * LLM errors
* Paginated document list (10 items per page)
* Type-based filtering (works with pagination)

---

## Architecture

### High-Level Structure

```
documents/
├── views.py            # HTTP endpoints & access control
├── models.py           # Document, Notebook, Conversation, Message
├── services/
│   ├── upload/          # Validation & limits
│   ├── pipeline/        # Orchestration (extract → analyze → save)
│   ├── analysis/        # Summarizer, classifier, language detection
│   ├── chat/            # Context building & chat logic
│   ├── llm/             # LLM client, guardrails, logging
│   └── storage/         # File organization (optional)
```

The architecture keeps:

* Views thin
* Business logic testable
* LLM usage isolated and auditable

---

## Processing Flow

### Single Document

Upload → Validate → Save File → Extract Text → Metadata → LLM Summary & Type → Persist → Detail View

### Notebook (Multiple Documents)

Upload / Select → Per-Doc Summaries → AI Title → Consolidated Summary → Notebook View

### Chat (Streaming)

Open Chat → Send Message → Save User Message → Stream Tokens → Save Final Assistant Message (unless canceled)

---

## Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL
* **LLM Providers:**

  * Ollama (local)
  * AWS Bedrock (Claude 3.5)
* **Frontend:** Django Templates, Tailwind CSS
* **Streaming:** Server-Sent Events (SSE)
* **Auth:** Django Authentication System

---

## Limitations

* No OCR for scanned PDFs
* Synchronous processing (no background workers)
* Designed for low-to-moderate concurrency
* Prototype-level security hardening

---

## Future Improvements

* Background jobs (Celery / RQ)
* Embedding-based semantic retrieval
* Amazon S3 + CloudFront integration
* Team-based notebooks and sharing
* Advanced usage analytics
* Fine-grained role-based access control


