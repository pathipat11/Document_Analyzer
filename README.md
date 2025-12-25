# Document Intake & Analysis System (Local Prototype)

## Overview
A local Django web app that ingests documents, extracts text, generates metadata (word/char counts), optionally classifies document type, and produces a short summary using a local LLM (Ollama). Data is stored in PostgreSQL and files are stored in local media storage.

## Features
- Upload documents (.txt, .csv, .pdf, .docx)
- File validation (type + max size 5MB)
- Text extraction + word_count/char_count
- Short summary (2–3 sentences) via local Ollama
- Document list + detail page
- Filter by document_type
- Export metadata as CSV
- Admin panel customization

## Architecture
- `documents/views.py`: thin HTTP layer
- `documents/services/`:
  - `text_extractor.py`: extract text per file type
  - `processor.py`: pipeline orchestration
  - `llm_client.py`: Ollama wrapper
  - `summarizer.py`: summary generation
  - `classifier.py`: document_type classification
- `documents/models.py`: `Document` entity

## Flow Diagram
Upload → Validate → Save file (media/) → Extract text → Compute counts → (Optional) LLM summary/type → Save to DB → List/Detail UI

## Tech Stack
- Python, Django
- PostgreSQL (local)
- Ollama (local LLM)
- Tailwind (optional styling)

## Setup (Local)
1. Create and activate venv
2. Install requirements
3. Configure `.env`
4. Run migrations
5. Start server
6. Ensure Ollama is running and the model is pulled (e.g. `llama3`)

## Limitations
- PDF text extraction works for text-based PDFs; scanned PDFs require OCR (not included).
- LLM output depends on local model availability and performance.
- Processing is synchronous (prototype). For production, use background jobs.

## Screenshots
(Add screenshots of upload/list/detail/admin)
