import os
import io
import re
import json
import base64
import streamlit as st
import pandas as pd
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from fpdf import FPDF
import datetime

def generate_professional_pdf(df, project_name="Project Estimate"):
    pdf = FPDF()
    pdf.add_page()
    
    # --- Header ---
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(44, 62, 80) # Dark Blue
    pdf.cell(0, 10, "SPACE CRAFT - Interior Design Estimate & Work Plan", ln=True, align="C")
    pdf.ln(5)
    
    # Project Info
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, f"Project Name: {project_name}", ln=True, align="C")
    pdf.cell(0, 5, f"Date: {datetime.date.today().strftime('%B %d, %Y')}", ln=True, align="C")
    pdf.ln(10)
    
    # Section 1: Overview
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, "1. Project Overview", ln=True)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    overview_text = "This document outlines the interior work breakdown for the project including woodwork, materials used, work scheduling, and payment terms."
    pdf.multi_cell(0, 5, overview_text)
    pdf.ln(5)
    
    # Section 2: Detailed Woodwork
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, "2. Detailed Woodwork Estimate", ln=True)
    
    # Table Header
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    cols = ["Item", "Measurement", "SFT", "Rate", "Amount"]
    widths = [65, 35, 25, 25, 40]
    
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 8, col, border=1, fill=True, align="C")
    pdf.ln()
    
    # Table Data Categorized by Room
    pdf.set_font("helvetica", "", 9)
    if not df.empty:
        rooms = df["category"].unique()
        for room in rooms:
            # Room Row
            pdf.set_font("helvetica", "B", 9)
            pdf.set_fill_color(250, 250, 250)
            pdf.cell(sum(widths), 7, f"  {room}", border=1, ln=True, fill=True)
            
            room_df = df[df["category"] == room]
            pdf.set_font("helvetica", "", 8)
            for _, row in room_df.iterrows():
                # Item (with wrap handle)
                x, y = pdf.get_x(), pdf.get_y()
                pdf.multi_cell(widths[0], 6, str(row['item_name']), border=1)
                new_y = pdf.get_y()
                
                # Move back to fill other columns
                pdf.set_xy(x + widths[0], y)
                pdf.cell(widths[1], new_y - y, str(row.get('measurement', '-')), border=1, align="C")
                pdf.cell(widths[2], new_y - y, f"{row.get('sft', 0):.2f}", border=1, align="C")
                pdf.cell(widths[3], new_y - y, f"{row.get('rate', 0):,.2f}", border=1, align="C")
                pdf.cell(widths[4], new_y - y, f"Rs. {row.get('amount', 0):,.2f}", border=1, align="R")
                pdf.ln()
    
    # Total
    total_val = df["amount"].sum() if not df.empty else 0
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(sum(widths[:-1]), 10, "GRAND TOTAL  ", border=1, align="R")
    pdf.cell(widths[-1], 10, f"Rs. {total_val:,.2f}", border=1, align="R")
    pdf.ln(15)
    
    # Section 3: Timeline & Payment (Standard Template)
    if pdf.get_y() > 220: pdf.add_page() # Check for space
    
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, "3. Work Execution Timeline", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 5, "- Execution duration: Approx 45 working days post-finalization.\n- Finishing stage: 7-9 working days after core framework completion.")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, "4. Payment Schedule", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 5, "- 10% At the time of Booking\n- 10% On sharing first design draft\n- 10% Upon completion of final design\n- 20% Upon finalization of materials\n- 30% At start of production\n- 10% At commencement of installation\n- 5% Midway through site execution\n- 5% On final cleaning and handover")
    
    return pdf.output()

# Try to import PyMuPDF (fitz).
HAVE_PYMUPDF = False
try:
    import fitz  # PyMuPDF
    import pymupdf
    HAVE_PYMUPDF = True
except Exception:
    HAVE_PYMUPDF = False

# Try to import pypdfium2
HAVE_PDFIUM = False
try:
    import pypdfium2 as pdfium
    HAVE_PDFIUM = True
except Exception:
    HAVE_PDFIUM = False

# Fallback for PDF to image conversion
HAVE_PDF2IMAGE = False
try:
    from pdf2image import convert_from_bytes
    HAVE_PDF2IMAGE = True
except Exception:
    HAVE_PDF2IMAGE = False

# Load environment variables from .env file
load_dotenv()

# Gemini configuration
USE_AI = False
client = None
try:
    # Use environment variable for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        client = genai.Client(api_key=api_key)
        USE_AI = True
except Exception:
    USE_AI = False


def extract_pages(uploaded_file):
    """Return a list of pages: [{"page": n, "content": text, "image_b64": base64_str}, ...].
    Uses multiple fallback methods to render pages to images.
    """
    pdf_bytes = uploaded_file.read()
    pages = []

    # Attempt method 1: PyMuPDF (fastest)
    if HAVE_PYMUPDF:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for i, page in enumerate(doc):
                text = page.get_text()
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img_b64 = base64.b64encode(img_data).decode("utf-8")
                pages.append({
                    "page": i + 1,
                    "content": text,
                    "image_b64": img_b64
                })
            if pages: return pages
        except Exception:
            pass

    # Attempt method 2: pypdfium2 (portable & fast)
    if HAVE_PDFIUM:
        try:
            pdf = pdfium.PdfDocument(pdf_bytes)
            for i, page in enumerate(pdf):
                # Get text
                text = ""
                try:
                    textpage = page.get_textpage()
                    text = textpage.get_text_bounded()
                except Exception:
                    pass
                
                # Render to image
                bitmap = page.render(scale=2)
                pil_img = bitmap.to_pil()
                buffered = io.BytesIO()
                pil_img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                pages.append({
                    "page": i + 1,
                    "content": text,
                    "image_b64": img_b64
                })
            if pages: return pages
        except Exception:
            pass

    # Attempt method 3: pdf2image (requires poppler installed)
    if HAVE_PDF2IMAGE:
        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            for i, img in enumerate(images):
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                pages.append({
                    "page": i + 1,
                    "content": "",
                    "image_b64": img_b64
                })
            if pages: return pages
        except Exception:
            pass

    # Method 3: Text Fallback (PyPDF2)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({
                "page": i + 1,
                "content": text,
                "image_b64": None
            })
        return pages
    except Exception as e:
        return [{"page": 1, "content": f"[Error extracting PDF: {e}]", "image_b64": None}]


@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(lambda e: "503" in str(e) or "overloaded" in str(e).lower())
)
def _call_gemini_with_retry(contents):
    """Internal helper to call Gemini with retries on transient errors."""
    return client.models.generate_content(
        model='gemini-flash-latest',
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
        )
    )

def analyze_page_ai(page_data):
    """Uses Gemini to analyze the page image or text and extract details."""
    if not USE_AI or client is None:
        return {"mode": "unknown", "items": []}

    image_b64 = page_data.get("image_b64")
    text_content = page_data.get("content", "")

    prompt = """
You are an expert interior design estimator and architectural analyzer.
Analyze the provided content (image or text). Determine if it is a structured estimate table or an architectural drawing.

### MODE 1: STRUCTURED ESTIMATE TABLE
If the page contains an estimate table (e.g., Living Room, Kitchen, Wardrobe categories with SFT, Rate, Amount), extract EVERY row.
JSON structure:
{
  "mode": "estimate",
  "items": [
    {
      "category": "Living Room",
      "item_name": "Acrolic TV Panaling + PU",
      "measurement": "5.2x7.4",
      "sft": 38.48,
      "rate": 1850.00,
      "amount": 71188.00
    }
  ]
}

### MODE 2: ARCHITECTURAL DRAWING
If the page is a drawing/blueprint, identify visual components.
JSON structure:
{
  "mode": "drawing",
  "items": [
    {
      "name": "Wall Cabinet",
      "dimension": "600 x 720 mm",
      "area": "0.43 sqm",
      "circumference": "2.64 m"
    }
  ]
}

Return the result as a STRICT JSON object. Ensure numerical values (sft, rate, amount) are numbers, not strings with currency symbols.
"""

    try:
        contents = [prompt]
        if image_b64:
            contents.append(types.Part.from_bytes(
                data=base64.b64decode(image_b64),
                mime_type="image/png"
            ))
        else:
            contents.append(f"PDF Content:\n{text_content}")

        response = _call_gemini_with_retry(contents)
        raw_text = response.text
        
        if st.session_state.get("debug_mode"):
            st.sidebar.subheader("Raw AI Response")
            st.sidebar.code(raw_text)

        result = json.loads(raw_text)
        
        # Robust Format Correction
        if isinstance(result, list):
            # AI returned just the list of items
            return {"mode": "estimate", "items": result}
        return result
    except Exception as e:
        st.error(f"AI Analysis Error: {e}")
        return {"mode": "error", "items": []}


def main():
    st.set_page_config(page_title="Interior Project Analyzer", layout="wide", page_icon="🏗️")
    
    # Custom CSS for a more "Interior Design" feel
    st.markdown("""
        <style>
        .main { background-color: #f8f9fa; }
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stTable { background-color: #ffffff; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🏢 Full-Scale Interior Project Analyzer")
    st.markdown("Transforming Architectural Drawings and Estimate Documents into Actionable Data.")

    st.sidebar.markdown("## ⚙️ Settings")
    st.session_state.debug_mode = st.sidebar.checkbox("🐞 Debug Mode", value=False)
    rendering_status = "✅ Vision Mode (Ready)" if (HAVE_PYMUPDF or HAVE_PDFIUM or HAVE_PDF2IMAGE) else "⚠️ Text-Only Mode"

    st.sidebar.write("System Engine:", rendering_status)
    st.sidebar.write("Gemini Status:", "✅ Active" if USE_AI else "❌ Offline")
    
    if not USE_AI:
        st.sidebar.warning("Missing GOOGLE_API_KEY in .env")

    uploaded_file = st.file_uploader("Upload PDF (Drawing or Estimate)", type=["pdf"])

    if not uploaded_file:
        st.info("👋 Welcome! Upload an interior design PDF to begin analysis.")
        return

    # Auto-clear results if a new file is uploaded
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        st.session_state.full_results = []
        st.session_state.current_file_name = uploaded_file.name
        # Clear individual page results
        for key in list(st.session_state.keys()):
            if key.startswith("res_"):
                del st.session_state[key]

    with st.spinner("📑 Loading PDF document..."):
        uploaded_file.seek(0)
        pages = extract_pages(uploaded_file)
    
    st.success(f"Loaded {len(pages)} pages.")

    if "full_results" not in st.session_state:
        st.session_state.full_results = []

    # Display and Analyze Pages
    for i, page in enumerate(pages):
        with st.expander(f"📄 Page {page['page']} Analysis", expanded=(i==0)):
            col1, col2 = st.columns([1, 1.2])
            
            with col1:
                if page["image_b64"]:
                    img_bytes = base64.b64decode(page["image_b64"])
                    st.image(img_bytes, caption=f"Page {page['page']} Visual", width="stretch")
                else:
                    st.info("Text-only content detected.")
                    st.text_area("Source Text", page["content"], height=200, key=f"text_{i}")
            
            with col2:
                btn_key = f"analyze_{i}"
                if st.button(f"🔍 Analyze Page {page['page']}", key=btn_key):
                    with st.spinner("🤖 AI is processing..."):
                        result = analyze_page_ai(page)
                        if result and result.get("mode") != "error":
                            st.session_state[f"res_{i}"] = result
                            # Append to aggregate if not already there
                            if result not in st.session_state.full_results:
                                st.session_state.full_results.append(result)
                            st.rerun()
                        else:
                            st.error("AI Analysis failed to return valid data. Please try again.")
                
                if f"res_{i}" in st.session_state:
                    res = st.session_state[f"res_{i}"]
                    if isinstance(res, dict):
                        mode = res.get("mode", "unknown")
                        items = res.get("items", [])
                        if mode == "estimate":
                            st.markdown("### 📊 Extracted Estimate Data")
                            df = pd.DataFrame(items)
                            st.dataframe(df, width="stretch")
                        elif mode == "drawing":
                            st.markdown("### 📐 Drawing Components")
                            st.table(items)
                        else:
                            st.warning("Could not categorize this page automatically.")
                    else:
                        st.error("AI returned data in an invalid format.")

    # Aggregate Analysis & Summary Dashboard
    if st.session_state.full_results:
        st.divider()
        st.header("📈 Project Dashboard & Summary")
        
        # Combine all estimate items
        all_estimate_items = []
        for r in st.session_state.full_results:
            if isinstance(r, dict) and r.get("mode") == "estimate":
                all_estimate_items.extend(r.get("items", []))
        
        if all_estimate_items:
            full_df = pd.DataFrame(all_estimate_items)
            
            # Key Metrics
            total_cost = full_df["amount"].sum()
            total_sft = full_df["sft"].sum()
            avg_rate = total_cost / total_sft if total_sft > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Project Cost", f"₹{total_cost:,.2f}")
            m2.metric("Total Area (SFT)", f"{total_sft:,.2f}")
            m3.metric("Avg Rate (₹/SFT)", f"₹{avg_rate:,.2f}")
            
            # Room Breakdown Chart
            st.subheader("Room-wise Cost Breakdown")
            if not full_df.empty and "category" in full_df.columns:
                room_costs = full_df.groupby("category")["amount"].sum().reset_index()
                st.bar_chart(room_costs.set_index("category"))
            
            # Full Data View
            with st.expander("📝 View Complete Itemized List", expanded=True):
                st.dataframe(full_df, width="stretch")
            
            # Export Options
            col_ex1, col_ex2, col_ex3 = st.columns(3)
            
            # PDF Professional Quote
            try:
                pdf_bytes = generate_professional_pdf(full_df, project_name=uploaded_file.name.replace(".pdf", ""))
                col_ex1.download_button("📜 Download Professional Quote (PDF)", pdf_bytes, "professional_quote.pdf", "application/pdf")
            except Exception as pdf_err:
                col_ex1.error(f"PDF Error: {pdf_err}")
                st.info("PDF generation failed, but you can still download CSV/JSON.")

            # CSV Export
            csv = full_df.to_csv(index=False).encode('utf-8')
            col_ex2.download_button("📥 Download Estimate (CSV)", csv, "interior_estimate.csv", "text/csv")

            # JSON Export
            json_str = json.dumps(all_estimate_items, indent=2)
            col_ex3.download_button("📥 Download Data (JSON)", json_str, "interior_data.json", "application/json")

        else:
            st.info("Analyze estimate pages to generate the project dashboard.")

if __name__ == "__main__":
    main()
