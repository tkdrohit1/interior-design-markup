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

# Try to import PyMuPDF (fitz).
HAVE_PYMUPDF = False
try:
    import fitz  # PyMuPDF
    import pymupdf
    HAVE_PYMUPDF = True
except Exception:
    HAVE_PYMUPDF = False

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

    # Attempt method 2: pdf2image (requires poppler installed)
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

        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
            )
        )
        return json.loads(response.text)
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
    rendering_status = "✅ Vision Mode (Ready)" if (HAVE_PYMUPDF or HAVE_PDF2IMAGE) else "⚠️ Text-Only Mode"
    st.sidebar.write("System Engine:", rendering_status)
    st.sidebar.write("Gemini Status:", "✅ Active" if USE_AI else "❌ Offline")
    
    if not USE_AI:
        st.sidebar.warning("Missing GOOGLE_API_KEY in .env")

    uploaded_file = st.file_uploader("Upload PDF (Drawing or Estimate)", type=["pdf"])

    if not uploaded_file:
        st.info("👋 Welcome! Upload an interior design PDF to begin analysis.")
        return

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
                    st.image(img_bytes, caption=f"Page {page['page']} Visual", use_container_width=True)
                else:
                    st.info("Text-only content detected.")
                    st.text_area("Source Text", page["content"], height=200, key=f"text_{i}")
            
            with col2:
                btn_key = f"analyze_{i}"
                if st.button(f"🔍 Analyze Page {page['page']}", key=btn_key):
                    with st.spinner("🤖 AI is processing..."):
                        result = analyze_page_ai(page)
                        st.session_state[f"res_{i}"] = result
                        # Append to aggregate if not already there
                        if result not in st.session_state.full_results:
                            st.session_state.full_results.append(result)
                
                if f"res_{i}" in st.session_state:
                    res = st.session_state[f"res_{i}"]
                    if res["mode"] == "estimate":
                        st.markdown("### 📊 Extracted Estimate Data")
                        df = pd.DataFrame(res["items"])
                        st.dataframe(df, use_container_width=True)
                    elif res["mode"] == "drawing":
                        st.markdown("### 📐 Drawing Components")
                        st.table(res["items"])
                    else:
                        st.warning("Could not categorize this page automatically.")

    # Aggregate Analysis & Summary Dashboard
    if st.session_state.full_results:
        st.divider()
        st.header("📈 Project Dashboard & Summary")
        
        # Combine all estimate items
        all_estimate_items = []
        for r in st.session_state.full_results:
            if r.get("mode") == "estimate":
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
            room_costs = full_df.groupby("category")["amount"].sum().reset_index()
            st.bar_chart(room_costs.set_index("category"))
            
            # Full Data View
            with st.expander("📝 View Complete Itemized List", expanded=True):
                st.dataframe(full_df, use_container_width=True)
            
            # Export Options
            col_ex1, col_ex2 = st.columns(2)
            csv = full_df.to_csv(index=False).encode('utf-8')
            col_ex1.download_button("📥 Download Estimate (CSV)", csv, "interior_estimate.csv", "text/csv")
            
            json_str = json.dumps(all_estimate_items, indent=2)
            col_ex2.download_button("📥 Download Data (JSON)", json_str, "interior_data.json", "application/json")
        else:
            st.info("Analyze estimate pages to generate the project dashboard.")

if __name__ == "__main__":
    main()
