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

* **Map step**: generate per-document lightweight summaries
* **Reduce step**:

  * Generate a consolidated summary across all documents
  * Produce an AI-generated notebook title

Each notebook contains:

* Title
* Combined summary
* Linked source documents
* Aggregate metadata (document count, total words)

> The combined summary is intentionally optimized to avoid re-summarizing full documents, reducing token usage while preserving cross-document themes.

---

### 5. Smart Chat Routing (Document vs General Chat)

The chat system supports **dual-mode conversation routing**:

* **Document-aware mode** — answers grounded in document content
* **General chat mode** — behaves like a normal assistant

#### Automatic Mode Detection

* The system evaluates whether a user question is relevant to the document by:

  * Keyword overlap scoring
  * Stopword filtering (Thai + English)
  * Minimum relevance thresholds

If a question is deemed **unrelated** to the document, the assistant:

* Responds naturally without referencing files
* Avoids misleading document-based answers

#### Manual Override (Optional)

Users can explicitly control routing:

* `@doc <question>` → force document-based answering
* `@chat <question>` → force general chat mode

---

### 6. Retrieval-Augmented Chat (RAG-lite)

For document-based chat:

* The system retrieves **top relevant text chunks** per question
* Chunks are scored using term overlap heuristics
* Only relevant excerpts are injected into the prompt

Benefits:

* Reduced context size
* Higher factual accuracy
* Lower token usage

Citations are internally tracked using excerpt IDs (e.g. `[C3]`) without exposing file-centric language to users.

---

### 7. Streaming Chat with Cancellation (ChatGPT-like UX)

* Server-Sent Events (SSE) token streaming
* Tokens appear in real time
* Single-button UX:

  * `Send` → `Cancel`

#### Dual Cancellation Safety

* Client-side abort (`AbortController`)
* Server-side cancel flag (prevents DB writes)

Guarantees:

* No partial assistant messages saved
* No unnecessary token usage
* Clean conversation history

---

### 8. LLM Architecture (Local + Cloud)

LLM access is abstracted behind a unified service layer.

#### Supported Providers

* **Ollama (local-first)** — development & experimentation
* **AWS Bedrock (Claude 3.5 Haiku via Inference Profile ARN)** — managed production-style inference

Switching providers:

```env
LLM_PROVIDER=bedrock  # or ollama
```

#### Unified LLM Client

* `generate_text(...)` — synchronous inference
* `generate_text_stream(...)` — streaming inference
* Provider-agnostic interface
* Centralized logging via `LLMCallLog`

---

### 9. Guardrails, Quotas & Cost Control

To prevent runaway usage:

* **Daily per-user call limits**
* **Per-feature token budgets** (chat vs upload/analysis)
* Preflight token estimation before execution

If limits are exceeded:

* Requests are blocked early
* Clear error messages are returned (`429`)
* UI displays remaining quota and reset time

---

### 10. Storage Abstraction (Local → S3 Ready)

* Uses Django storage abstraction (`FileField` + storage backend)
* File access via streams (no filesystem coupling)
* Compatible with private Amazon S3 buckets
* Ready for pre-signed download URLs

---

### 11. User Interface & UX

* Django Templates + Tailwind CSS

* Responsive layout

* Light / Dark mode toggle (persisted client-side)

* Toast notifications for:

  * Upload results
  * Deletions
  * LLM quota errors

* Paginated document list (10 items per page)

* Type-based filtering with pagination preservation

---

## Architecture

```
documents/
├── views.py            # HTTP endpoints & access control
├── models.py           # Document, Notebook, Conversation, Message
├── services/
│   ├── upload/          # Validation & limits
│   ├── pipeline/        # Extract → analyze → persist
│   ├── analysis/        # Summarizer, classifier, language detection
│   ├── chat/            # Routing, retrieval, streaming chat
│   ├── llm/             # Providers, guardrails, token ledger
│   └── storage/         # File organization (S3-ready)
```

Design goals:

* Thin views
* Testable services
* Auditable LLM usage

---

## Processing Flow

### 1. Single Document Upload Flow

```
User Upload
   ↓
Validation (size / count / type)
   ↓
File Storage (Django storage abstraction)
   ↓
Text Extraction
   ↓
Metadata Analysis (word / char count)
   ↓
LLM Summarization + Classification
   ↓
Persist Document
   ↓
Document Detail View
```

Key characteristics:

* Fully synchronous (prototype-friendly)
* Each step is isolated in a service layer
* Safe to migrate into background workers later

---

### 2. Multiple Documents → Notebook Flow

```
Upload or Select Multiple Documents
   ↓
Per-Document Summaries (Map step)
   ↓
Title Generation
   ↓
Consolidated Summary (Reduce step)
   ↓
Notebook (CombinedSummary) Created
   ↓
Notebook Detail View
```

Design notes:

* Map summaries are reused where possible
* Reduce step operates on summaries, not raw text (cost-efficient)
* Notebook keeps references to original documents

---

### 3. Chat (Streaming) Flow

```
Open Chat View
   ↓
User Sends Message
   ↓
Save User Message
   ↓
Context Assembly
   ↓
LLM Streaming Response (SSE)
   ↓
Token-by-token UI Update
   ↓
Final Assistant Message Saved
```

If canceled:

```
Cancel Triggered
   ↓
Abort Stream (Client)
   ↓
Stop Generation (Server)
   ↓
No Assistant Message Saved
```

---

### 4. Smart Chat Routing Flow

```
User Question
   ↓
Heuristic Check (general vs document-related)
   ↓
├─ Document-related → Retrieval + Context
└─ General question → Plain Chat Mode
   ↓
LLM Response
```

This approach:

* Prevents hallucinated file references
* Improves answer relevance
* Keeps UX similar to normal chat when appropriate

---

## Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL
* **LLM Providers:** Ollama, AWS Bedrock (Claude 3.5)
* **Frontend:** Django Templates, Tailwind CSS
* **Streaming:** Server-Sent Events (SSE)
* **Auth:** Django Authentication System

---

## Future Improvements

* Background jobs (Celery / RQ)
* Embedding-based semantic retrieval
* Amazon S3 + CloudFront integration
* Team-based notebooks and sharing
* Advanced usage analytics
* Role-based access control
