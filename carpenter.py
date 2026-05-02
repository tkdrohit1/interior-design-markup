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
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "KITCHEN MODULAR QUOTATION", ln=True, align="C")
    pdf.ln(5)
    
    # Project Info
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, f"Project: {project_name}", ln=True, align="L")
    pdf.cell(0, 5, f"Date: {datetime.date.today().strftime('%d/%m/%Y')}", ln=True, align="L")
    pdf.ln(10)
    
    # Table Header (Jeeva Style)
    # Location | Measurements (in Feet) | Total Sq.ft | Rate per Sq.ft | Total Amount
    pdf.set_font("helvetica", "B", 9)
    cols = ["Location", "Measurements (in Feet)", "Total Sq.ft", "Rate per Sq.ft", "Total Amount"]
    widths = [50, 45, 25, 30, 40]
    
    # Draw Headers
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 8, col, border=1, align="C")
    pdf.ln()
    
    # Table Data
    pdf.set_font("helvetica", "", 8)
    if not df.empty:
        for _, row in df.iterrows():
            # Handle long item names by wrapping in 'Location' column
            x, y = pdf.get_x(), pdf.get_y()
            
            # Combine category and item name for 'Location'
            # Replace en-dash with standard hyphen for PDF compatibility
            location_text = f"{row['category']}: {row['item_name']}".replace("–", "-").replace("—", "-")
            pdf.multi_cell(widths[0], 6, location_text, border=1)
            new_y = pdf.get_y()
            h = new_y - y
            
            # Reset position for other columns in the same row
            pdf.set_xy(x + widths[0], y)
            pdf.cell(widths[1], h, str(row.get('measurement', '-')), border=1, align="C")
            pdf.cell(widths[2], h, f"{row.get('sft', 0):.2f}", border=1, align="C")
            pdf.cell(widths[3], h, f"Rs. {row.get('rate', 0):,.2f}", border=1, align="C")
            pdf.cell(widths[4], h, f"Rs. {row.get('amount', 0):,.2f}", border=1, align="R")
            pdf.ln()
    
    # Grand Total
    total_val = df["amount"].sum() if not df.empty else 0
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(sum(widths[:-1]), 10, "GRAND TOTAL  ", border=1, align="R")
    pdf.cell(widths[-1], 10, f"Rs. {total_val:,.2f}", border=1, align="R")
    
    # Standard Material Specs (As typically expected in modular quotes)
    pdf.ln(20)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 10, "Material Specifications:", ln=True)
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 5, "- Carcass: BWP Plywood (710 Grade)\n- Finish: 1.0mm Glossy/Matt Laminate or Acrylic\n- Hardware: Soft-close hinges and tandem boxes (Hettich/Hafele/Equivalent)\n- Edgebending: PVC 2mm machine pressed")
    
    output = pdf.output()
    if isinstance(output, bytearray):
        return bytes(output)
    return output

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
    """Uses Gemini to analyze the page image or text and extract details specialized for Kitchen Modular Drawings."""
    if not USE_AI or client is None:
        return {"mode": "unknown", "items": []}

    image_b64 = page_data.get("image_b64")
    text_content = page_data.get("content", "")

    prompt = """
You are a Senior Kitchen Modular Estimator. 
Analyze the provided drawing. Your goal is to provide a CONSOLIDATED RUNNING LENGTH estimate, exactly how a contractor bills.

### CALCULATION RULES (CRITICAL):
1. **NO DOUBLE COUNTING**: Do not add individual cabinets if you can see the total run length. 
2. **Consolidate by Category**: Group all base cabinets on one wall into a single "Kitchen - Base Unit" entry.
3. **Dimensions**: Convert MM to Feet (MM / 304.8).
4. **SFT Calculation**: SFT = Length(ft) x Height(ft).
5. **Categories to Use**:
   - "Kitchen – Base Unit (BWP)" (Standard height approx 2.9ft)
   - "Kitchen – Middle Unit" (Wall units, standard height approx 2.4ft)
   - "Kitchen – Loft" (Top units, standard height approx 1.9ft)
   - "Kitchen – Rolling Box (BWP)" (Full height units)

### JEEVA STYLE SCHEMA:
{
  "mode": "estimate",
  "items": [
    {
      "category": "Kitchen – Base Unit (BWP)",
      "item_name": "Main Counter Run (Consolidated)",
      "measurement": "16.2 x 2.9",
      "sft": 47.0,
      "rate": 1800.00,
      "amount": 84600.00
    }
  ]
}

### LOGIC:
- If you see an L-shape, subtract the corner overlap (usually 2ft) so the SFT is accurate.
- If rates are not visible, use: Base ₹1800, Middle ₹1600, Loft ₹1100, Rolling Box ₹1800.

Return STRICT JSON.
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
    st.set_page_config(
        page_title="Interior Project Analyzer | AI Studio", 
        layout="wide", 
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )
    
    # --- MODERN ARCHITECTURAL CSS ---
    st.markdown("""
        <style>
        /* Base Styles */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        .main {
            background-color: #fcfcfd;
        }
        
        /* Card-based UI */
        div[data-testid="stExpander"] {
            background-color: white;
            border: 1px solid #eef0f2;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
        }
        
        /* Metric Styling */
        div[data-testid="stMetric"] {
            background-color: white;
            border: 1px solid #eef0f2;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        
        /* Modern Buttons */
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 3em;
            background-color: #1a1a1a;
            color: white;
            border: none;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #404040;
            border: none;
            color: white;
            transform: translateY(-2px);
        }
        
        /* Header Styling */
        .main-header {
            font-size: 2.5rem;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 0.5rem;
        }
        .sub-header {
            font-size: 1.1rem;
            color: #666;
            margin-bottom: 2rem;
        }
        
        /* Floating Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #eef0f2;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- TOP HEADER ---
    st.markdown('<h1 class="main-header">🏗️ AI Studio</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Premium Interior Quotation Engine & Blueprint Analyzer</p>', unsafe_allow_html=True)

    # --- SIDEBAR CONFIGURATION ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/1033/1033001.png", width=80)
        st.title("Studio Settings")
        
        with st.expander("💰 Price List (₹/SFT)", expanded=True):
            rate_base = st.number_input("Base Unit", value=1850, step=50)
            rate_wall = st.number_input("Wall Unit", value=1550, step=50)
            rate_tall = st.number_input("Tall Unit", value=2200, step=50)
            rate_loft = st.number_input("Loft Unit", value=1250, step=50)

        st.session_state.current_rates = {
            "Base": rate_base,
            "Wall": rate_wall,
            "Tall": rate_tall,
            "Loft": rate_loft
        }
        
        st.divider()
        st.session_state.debug_mode = st.checkbox("🐞 Debug Mode", value=False)
        
        st.caption("v2.0 | Architectural Edition")

    # --- UPLOAD SECTION ---
    uploaded_file = st.file_uploader("", type=["pdf"])

    if not uploaded_file:
        st.info("✨ **Studio Ready.** Upload a drawing PDF to begin your specialized modular quotation.")
        return

    # Dynamic Project Naming
    raw_name = uploaded_file.name.replace(".pdf", "")
    project_name = re.sub(r'[\(\)\[\]]', '', raw_name).strip()

    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        st.session_state.full_results = []
        st.session_state.current_file_name = uploaded_file.name
        for key in list(st.session_state.keys()):
            if key.startswith("res_"): del st.session_state[key]

    with st.spinner("🖋️ Scanning blueprint..."):
        uploaded_file.seek(0)
        pages = extract_pages(uploaded_file)
    
    # --- PAGE ANALYSIS TABS ---
    st.markdown(f"### 📑 Project: {project_name}")
    
    # Display Pages in a polished grid
    for i, page in enumerate(pages):
        with st.expander(f"PAGE {page['page']} - Drawing Visualization", expanded=(i==0)):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("#### 🖼️ Blueprint View")
                if page["image_b64"]:
                    img_bytes = base64.b64decode(page["image_b64"])
                    st.image(img_bytes, use_container_width=True)
                else:
                    st.warning("Visual data not available for this page.")
            
            with col2:
                st.markdown("#### 🤖 AI Analysis")
                if f"res_{i}" not in st.session_state:
                    if st.button(f"Analyze Drawing {page['page']}", key=f"btn_{i}"):
                        with st.spinner("Calculating modules..."):
                            result = analyze_page_ai(page)
                            if result and result.get("mode") != "error":
                                st.session_state[f"res_{i}"] = result
                                if result not in st.session_state.full_results:
                                    st.session_state.full_results.append(result)
                                st.rerun()
                else:
                    res = st.session_state[f"res_{i}"]
                    items = res.get("items", [])
                    st.dataframe(pd.DataFrame(items), use_container_width=True)
                    if st.button("🗑️ Reset Page Data", key=f"reset_{i}"):
                        del st.session_state[f"res_{i}"]
                        st.rerun()

    # --- FINAL DASHBOARD ---
    if st.session_state.full_results:
        st.divider()
        st.markdown("### 📊 Quotation Dashboard")
        
        all_items = []
        for r in st.session_state.full_results:
            if r.get("mode") == "estimate": all_items.extend(r.get("items", []))
        
        if all_items:
            full_df = pd.DataFrame(all_items)
            
            # Key Metrics Cards
            c1, c2, c3 = st.columns(3)
            c1.metric("Project Total", f"₹{full_df['amount'].sum():,.2f}")
            c2.metric("Total Area", f"{full_df['sft'].sum():,.2f} SFT")
            c3.metric("Item Count", len(full_df))
            
            # Export Actions
            st.markdown("#### 📤 Export & Delivery")
            ex1, ex2, ex3 = st.columns(3)
            
            pdf_bytes = generate_professional_pdf(full_df, project_name=project_name)
            ex1.download_button("📜 Download JEEVA Style PDF", pdf_bytes, f"Quote_{project_name}.pdf", "application/pdf")
            
            csv = full_df.to_csv(index=False).encode('utf-8')
            ex2.download_button("📥 Download Excel/CSV", csv, f"Data_{project_name}.csv", "text/csv")
            
            st.success("✅ Quotation generated and ready for delivery.")

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
