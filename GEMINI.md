# 🏢 Interior Project Analyzer - GEMINI.md

This document provides foundational mandates and architectural guidance for the **Full-Scale Interior Project Analyzer**. These instructions take precedence over general defaults.

## 🎯 Project Vision
An intelligent tool for Interior Designers and Architects to bridge the gap between static PDF documents (blueprints/estimates) and actionable digital data using Gemini Vision.

## 🛠️ Core Tech Stack
- **AI Engine:** `google-genai` (SDK v1) using `gemini-flash-latest`.
- **UI Framework:** Streamlit (Python).
- **PDF Processing:** 
  - Primary: `PyMuPDF` (fitz) for speed and quality.
  - Fallback 1: `pdf2image` (requires Poppler).
  - Fallback 2: `PyPDF2` (text extraction only).
- **Data Handling:** Pandas for tabular data and financial summaries.

## 📋 Architectural Mandates

### 1. AI Interaction & Extraction
- **Model Choice:** Always prioritize `gemini-flash-latest` for its speed and cost-effectiveness in vision tasks.
- **JSON Enforcement:** Use `response_mime_type='application/json'` in the `GenerateContentConfig` to ensure strict schema compliance.
- **Dual Mode Support:** Maintain the distinction between `estimate` mode (tabular data) and `drawing` mode (visual components).

### 2. PDF Rendering Strategy
- **Visual-First:** Since interior documents rely heavily on visual context, prioritize image-based analysis over raw text extraction.
- **Fallback Chain:** Maintain the robust multi-engine rendering logic in `extract_pages` to ensure compatibility across different environments (local vs. Streamlit Cloud).

### 3. UI/UX Standards
- **Interior Design Aesthetic:** Use custom CSS to maintain a clean, professional "Architectural" feel (e.g., white cards, subtle shadows, proper spacing).
- **Progress Feedback:** Always use `st.spinner` or `st.progress` during heavy PDF processing or AI calls.
- **State Management:** Use `st.session_state` to persist analysis results across page re-runs to avoid redundant AI costs.

### 4. Code Standards
- **Error Handling:** Gracefully handle missing API keys, Poppler installation issues, or PDF corruption.
- **Environment Variables:** Strictly use `python-dotenv` for local development and Streamlit Secrets for cloud deployment.

## 🔒 Security & Safety
- **Credential Protection:** NEVER commit `.env` or log `GOOGLE_API_KEY`.
- **Data Privacy:** Do not store uploaded PDFs on the server; process them in-memory as bytes/base64.

## 🧪 Validation & Testing
- **Manual Verification:** Since automated testing of Vision models is complex, always manually verify extraction accuracy with `sample.pdf` when making changes to prompts or rendering logic.
- **Dependency Checks:** Verify the presence of system-level dependencies like Poppler when adding new image-processing features.
