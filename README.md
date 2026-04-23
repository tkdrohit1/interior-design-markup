# 🏢 Full-Scale Interior Project Analyzer

An intelligent Streamlit application that transforms complex **Architectural Drawings** (Blueprints) and **Interior Estimate Documents** into actionable, structured data using **Gemini Pro Vision**.

## 🚀 Features

- **Smart Mode Detection**: Automatically distinguishes between visual blueprints and structured estimate tables.
- **Architectural Vision**: Extracts component names, dimensions, area, and circumference from visual drawings.
- **Estimate Extraction**: Captures Room categories, Item names, Measurements, SFT, Rates, and total Amounts from tabular data.
- **Interactive Dashboard**:
    - **Financial Summary**: Total cost, Total area, and Average rate per SFT.
    - **Visual Breakdown**: Dynamic charts showing cost distribution by room.
    - **Itemized Tracking**: Searchable database of all project components.
- **Multi-Engine Rendering**: Robust PDF-to-image conversion with fallbacks for maximum compatibility.
- **Data Export**: Export results to **CSV** (for Excel) or **JSON**.

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **AI Engine**: [Google Gemini Pro (Vision & Text)](https://ai.google.dev/)
- **PDF Processing**: PyMuPDF, pdf2image, PyPDF2
- **Data Analysis**: Pandas

## 💻 Local Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:tkdrohit1/interior-design-markup.git
   cd interior-design-markup
   ```

2. **Install Poppler (Required for Vision fallback)**:
   - **Windows**: Download from [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) and add the `bin` folder to your System PATH.
   - **Linux**: `sudo apt-get install poppler-utils`

3. **Install dependencies**:
   ```bash
   python -m pip install -r requirements.txt
   ```

4. **Configure API Key**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

5. **Run the application**:
   ```bash
   streamlit run carpenter.py
   ```

## ☁️ Deployment (Streamlit Community Cloud)

1. **Push your code to GitHub** (Ensure `.env` is ignored!).
2. Go to [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub repository.
4. **Important**: Add your `GOOGLE_API_KEY` to the **App Secrets** in the Streamlit Cloud dashboard:
   ```toml
   GOOGLE_API_KEY = "your_actual_key_here"
   ```
5. Click **Deploy**!

---
Developed with 🏗️ for Interior Designers and Architects.
