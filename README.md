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

---

## Tech Stack

* **Backend:** Python, Django
* **Database:** PostgreSQL (local)
* **LLM:** Ollama (local model, e.g. `llama3`)
* **Frontend:** Django Templates + Tailwind CSS
* **Auth:** Django Authentication System

---

## Local Setup

1. Create and activate a virtual environment
2. Install Python dependencies
3. Configure environment variables in `.env`
4. Run database migrations
5. Start the Django development server
6. Ensure Ollama is running and the required model is pulled

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

## Screenshots

(Add screenshots of upload page, document list, document detail, combined summary, and admin panel)
