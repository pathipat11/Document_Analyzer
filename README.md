# Document Intake & Analysis System

## Overview

**Document Intake & Analysis System** is a Django-based document processing and AI analysis platform designed to ingest, analyze, summarize, search, and interact with documents using Large Language Models (LLMs).

The system supports both:

* **Local-first development** (Ollama)
* **Cloud inference via AWS Bedrock (Claude 3.5 Haiku – Inference Profile ARN)**

It is structured as a clean, service-oriented prototype that demonstrates production-style architecture patterns including streaming, cancellation safety, storage abstraction, quota control, and PostgreSQL full-text search.

---

# Core Capabilities

## 1. Secure Document Management

* Django authentication system
* Per-user document isolation (ownership enforced in queries)
* Upload single or multiple files
* Supported formats:

  * `.txt`
  * `.csv`
  * `.pdf` (text-based)
  * `.docx`
* Upload validation:

  * Max file size
  * Max total upload size
  * Max files per request
* Safe deletion:

  * Removes file from storage (local or S3)
  * Deletes DB record
  * Preserves pagination and filters

---

## 2. Storage Architecture (S3 + Presigned URLs)

* Django storage abstraction (`FileField` backend)
* Compatible with local storage or **private Amazon S3 buckets**
* Secure downloads via **pre-signed URLs**
* Inline file preview using secure `Content-Disposition`
* No direct public file exposure

This enables safe cloud deployment without rewriting file logic.

---

## 3. Text Extraction & Metadata Pipeline

Each uploaded document is processed synchronously through a structured pipeline:

* Text extraction by file type
* Word count calculation
* Character count calculation
* Extracted text persisted in database

> OCR is intentionally excluded to keep the prototype focused and deterministic.

---

## 4. AI-Powered Analysis

### 4.1 Document Summarization

* Short, concise summaries
* Language-aware output (Thai / English auto-detected)
* Optimized prompt length for token efficiency

### 4.2 Automatic Classification

Documents are classified into strict single-label types:

* `invoice`
* `announcement`
* `policy`
* `proposal`
* `report`
* `research`
* `resume`
* `other`

Classification is enforced via strict prompt formatting.

---

## 5. PostgreSQL Full-Text Search

Advanced search powered by:

* `SearchVector`
* `SearchQuery` (websearch mode)
* `SearchRank`
* `SearchHeadline` (snippet extraction)

Features:

* Keyword-based search
* Ranked ordering
* Extracted text snippets
* Filename matching
* Type filtering
* Date filtering
* Pagination preserved

This enables fast, scalable document lookup without external search engines.

---

## 6. Notebook-Style Multi-Document Analysis (Map–Reduce)

Supports combined analysis across multiple documents.

### Creation Methods

* Auto-combine on multi-file upload
* Manual combine from document list

### Processing Strategy

**Map Step**:

* Reuse or generate per-document summaries

**Reduce Step**:

* Generate consolidated cross-document summary
* AI-generated notebook title

Notebook contains:

* Title
* Combined summary
* Linked documents
* Document count
* Aggregate word count

Designed for token efficiency (reduce step operates on summaries only).

---

## 7. Retrieval-Augmented Chat (RAG-lite)

For document-aware chat:

* Relevant text chunks are selected per question
* Heuristic term overlap scoring
* Only top excerpts injected into prompt
* Reduced context size
* Improved factual grounding

Prevents unnecessary full-document prompt injection.

---

## 8. Smart Chat Routing

Dual-mode conversation handling:

* **Document-aware mode**
* **General assistant mode**

Automatic routing based on:

* Keyword overlap
* Stopword filtering (Thai + English)
* Relevance thresholds

Manual override supported:

* `@doc <question>` → force document mode
* `@chat <question>` → force general mode

Prevents hallucinated document references.

---

## 9. Real-Time Streaming Chat (SSE)

ChatGPT-style streaming using Server-Sent Events.

Features:

* Token-by-token streaming
* Cancel button
* Dual cancellation safety:

  * Client abort
  * Server-side cancellation flag
* Prevents partial assistant message saves
* Guarantees clean conversation history

---

## 10. Usage Monitoring & Token Ledger

Per-user daily token budgets:

* Separate budgets for:

  * Chat
  * Upload / Analysis
* Remaining quota tracking
* Automatic reset at midnight (timezone aware)
* Usage API for UI display
* Visual usage indicators (low / empty states)

Prevents runaway cost and enforces guardrails.

---

## 11. LLM Architecture (Provider-Agnostic)

Unified client layer:

* `generate_text()`
* `generate_text_stream()`

Supported providers:

* Ollama (local)
* AWS Bedrock – Claude 3.5 Haiku (Inference Profile ARN)

Switch via environment:

```
LLM_PROVIDER=bedrock
```

Inference Profile example:

```
BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:region:account:inference-profile/...
```

Design ensures no provider-specific logic leaks into views.

---

## 12. CSV Export

* Export documents as CSV
* Preserves filtering (type-based export)
* Includes metadata and summaries

---

## 13. User Interface & UX

* Django Templates + Tailwind CSS
* Responsive layout
* Landing page with animated hero + typing preview
* Dark / Light mode toggle
* Toast notifications
* Pagination (10 items per page)
* Preserved filters across navigation
* Usage dropdown with live refresh

---

# Architecture

```
documents/
├── views.py
├── models.py
├── services/
│   ├── upload/
│   ├── pipeline/
│   ├── analysis/
│   ├── chat/
│   ├── llm/
│   └── storage/
```

Design Principles:

* Thin views
* Service-layer isolation
* Provider abstraction
* Cancel-safe streaming
* Token-aware prompt design
* PostgreSQL-native search

---

# Processing Flows

## 1. Upload Flow

```
Upload
  ↓
Validation
  ↓
Storage (Local or S3)
  ↓
Extraction
  ↓
Metadata
  ↓
Summarization + Classification
  ↓
Persist
```

---

## 2. Combined Summary Flow

```
Select Multiple Docs
  ↓
Map (per-doc summaries)
  ↓
Generate Title
  ↓
Reduce (cross-doc summary)
  ↓
Create Notebook
```

---

## 3. Streaming Chat Flow

```
User Message
  ↓
Save User
  ↓
Context Assembly
  ↓
LLM Stream (SSE)
  ↓
Token Streaming
  ↓
Save Assistant
```

Cancellation Path:

```
Cancel
  ↓
Abort Client
  ↓
Stop Server
  ↓
No Save
```

---

# Tech Stack

* Python
* Django
* PostgreSQL
* AWS Bedrock (Claude 3.5)
* Ollama
* Tailwind CSS
* Server-Sent Events (SSE)

---

# Future Roadmap

* Background job queue (Celery / RQ)
* Embedding-based semantic retrieval
* Team workspaces
* Role-based access control
* Advanced analytics dashboard
* CloudFront integration
* Asynchronous processing pipeline

---

This project demonstrates a structured, production-aware AI document workflow with clean separation of concerns and scalable architectural foundations.
