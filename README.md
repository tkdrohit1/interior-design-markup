Interior Drawing Analyzer

This Streamlit app extracts text from PDF drawings and runs simple rule-based extraction.

Why you saw the DLL error
- PyMuPDF (pymupdf) includes native DLLs. On some Windows setups a missing dependency causes "ImportError: DLL load failed while importing _extra".

What I changed
- The app now tries to import PyMuPDF, but if that fails it falls back to a pure-Python extraction using PyPDF2 so the app won't crash.

Quick setup (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
# If you want PyMuPDF (optional), install the wheel that matches your Python version and architecture:
# python -m pip install pymupdf
streamlit run carpenter.py
```

If you still want PyMuPDF working, install a matching binary wheel for your Python version from PyPI or Christoph Gohlke's unofficial binaries.
