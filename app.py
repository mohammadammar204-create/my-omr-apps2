import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import zipfile
import json
import base64
import requests
import qrcode
import urllib.request
from PIL import Image
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="AI OMR Scanner & Generator", layout="wide")

st.title("📄 AI-Powered OMR Sheet Generator & Scanner")
st.write("Generate personalized bubble sheets and grade them using Gemini AI Vision.")

# ==================== API KEY RETRIEVAL ====================
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# ==================== ARABIC FONT SETUP ====================
FONT_PATH = "Amiri-Regular.ttf"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"

@st.cache_resource
def load_arabic_font():
    if not os.path.exists(FONT_PATH):
        try:
            req = urllib.request.Request(FONT_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                with open(FONT_PATH, "wb") as f:
                    f.write(response.read())
        except Exception:
            pass

    if os.path.exists(FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont('ArabicAmiri', FONT_PATH))
            return 'ArabicAmiri'
        except Exception:
            pass

    return 'Helvetica'

ARABIC_FONT = load_arabic_font()

if 'students_df' not in st.session_state:
    st.session_state.students_df = None

# ==================== SIDEBAR: ANSWER KEY ====================
st.sidebar.header("🔑 Set Correct Answer Key")
num_questions = st.sidebar.number_input("Number of Questions", min_value=5, max_value=100, value=25, step=5)

options = ["A", "B", "C", "D"]
answer_key = {}

st.sidebar.write("Select correct answers:")
sb_col1, sb_col2 = st.sidebar.columns(2)

for q in range(1, int(num_questions) + 1):
    target_col = sb_col1 if q <= (num_questions // 2 + num_questions % 2) else sb_col2
    answer_key[q] = target_col.selectbox(f"Q{q:02d}", options, index=0, key=f"ans_key_{q}")

tab1, tab2, tab3 = st.tabs(["1. Upload Student List", "2. Generate Pre-Printed Sheets", "3. Scan & Grade Sheets (AI)"])

# ==================== HELPER FUNCTIONS ====================
def load_student_dataframe(uploaded_file):
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.txt'):
        lines = uploaded_file.read().decode("utf-8").splitlines()
        df = pd.DataFrame({"Student Name": lines})
    
    name_col = None
    for col in df.columns:
        if any(keyword in str(col).lower() for keyword in ['name', 'اسم', 'طالب', 'student']):
            name_col = col
            break
            
    if name_col is None:
        name_col = df.columns[0]
        
    df = df.rename(columns={name_col: "Student Name"})
    return df

def reshape_arabic_text(text):
    if not text or str(text).lower() == 'nan':
        return ""
    clean_text = str(text).strip()
    reshaped_text = arabic_reshaper.reshape(clean_text)
    return get_display(reshaped_text)

def create_pdf_bytes(student_name, exam_title, total_q):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Registration Marks
    c.setFillColorRGB(0, 0, 0)
    c.rect(30, 742, 20, 20, fill=1)
    c.rect(562, 742, 20, 20, fill=1)
    c.rect(30, 30, 20, 20, fill=1)
    c.rect(562, 30, 20, 20, fill=1)
    
    # QR Code
    qr = qrcode.make(f"{student_name}")
    qr_pil = qr.get_image()
    qr_reader = ImageReader(qr_pil)
    c.drawImage(qr_reader, 470, 665, width=75, height=75)
    
    # Header Information
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 740, str(exam_title))
    
    formatted_name = reshape_arabic_text(student_name)
    c.setFont(ARABIC_FONT, 14)
    c.drawString(60, 705, f"Student Name: {formatted_name}")
    
    c.setLineWidth(1)
    c.line(60, 680, 542, 680)
    
    # Question Grid
    start_y = 650
    for q in range(1, total_q + 1):
        col_offset = ((q - 1) // 25) * 130
        row = (q - 1) % 25
        y = start_y - (row * 22)
        x_start = 60 + col_offset
        
        c.setFont("Helvetica", 9)
        c.drawString(x_start, y, f"{q:02d}:")
        for idx, opt in enumerate(options):
            bx = x_start + 25 + (idx * 20)
            c.circle(bx, y + 3, 6, stroke=1, fill=0)
            c.drawString(bx - 3, y, opt)
            
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

def process_omr_with_ai(img_bytes, total_q, key_dict, key):
    if not key:
        return "API Key Missing", 0

    base64_image = base64.b64encode(img_bytes).decode("utf-8")
    
    # REST Endpoint using direct header auth
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key.strip()
    }
    
    prompt = f"""
    Analyze this exam sheet image carefully.
    1. Extract the student name written next to "Student Name:" or decoded from the top QR code.
    2. Examine questions Q01 through Q{total_q:02d}.
    3. Determine which option (A, B, C, or D) is filled/shaded in pencil or pen. If unshaded, mark as null.
    
    Return ONLY a raw JSON object formatted like this:
    {{
      "student_name": "Extracted Student Name",
      "answers": {{
        "1": "A",
        "2": "B"
      }}
    }}
    """
    
    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = response.json()
        
        if response.status_code != 200:
            st.error(f"API Error ({response.status_code}): {res_json.get('error', {}).get('message', 'Unknown Error')}")
            return "Auth Error", 0
            
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw_text)
        
        extracted_name = data.get("student_name", "Unknown Student")
        detected_answers = data.get("answers", {})

        score = 0
        for q in range(1, total_q + 1):
            student_ans = detected_answers.get(str(q))
            correct_ans = key_dict.get(q)
            if student_ans and str(student_ans).upper() == str(correct_ans).upper():
                score += 1

        return extracted_name, score

    except Exception as e:
        st.error(f"AI Vision Processing Error: {e}")
        return "Processing Error", 0

# ==================== TAB 1 ====================
with tab1:
    st.header("📋 Step 1: Upload Class Roster")
    student_file = st.file_uploader("Upload class list (XLSX, CSV, TXT)", type=["xlsx", "xls", "csv", "txt"], key="tab1_student_file")
    if student_file is not None:
        try:
            st.session_state.students_df = load_student_dataframe(student_file)
            st.success(f"✅ Successfully loaded {len(st.session_state.students_df)} students!")
            st.dataframe(st.session_state.students_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error reading file: {e}")

# ==================== TAB 2 ====================
with tab2:
    st.header("🖨️ Step 2: Generate Pre-printed PDFs")
    col1, col2 = st.columns(2)
    with col1:
        exam_title = st.text_input("Exam Title", value="Midterm Exam 2026")
        tab2_file = st.file_uploader("Upload/Replace Excel Student List directly here", type=["xlsx", "xls", "csv", "txt"], key="tab2_student_file")
        if tab2_file is not None:
            st.session_state.students_df = load_student_dataframe(tab2_file)
            st.success(f"✅ Loaded {len(st.session_state.students_df)} students!")
            
    with col2:
        st.info("💡 Set the correct answer key for each question using the Sidebar on the left.")

    st.markdown("---")
    
    if st.session_state.students_df is None:
        st.warning("⚠️ Please upload a student Excel list using the button above or in Tab 1.")
    else:
        st.subheader(f"Ready to generate pre-printed sheets for {len(st.session_state.students_df)} students")
        if st.button("🚀 Generate All Student Sheets (ZIP File)"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, row in st.session_state.students_df.iterrows():
                    s_name = str(row["Student Name"])
                    pdf_bytes = create_pdf_bytes(s_name, exam_title, int(num_questions))
                    clean_filename = f"Sheet_{s_name.replace(' ', '_')}.pdf"
                    zip_file.writestr(clean_filename, pdf_bytes)
            
            zip_buffer.seek(0)
            st.success("🎉 All personalized PDFs generated successfully!")
            st.download_button(
                label="📥 Download All Sheets (ZIP Archive)",
                data=zip_buffer,
                file_name=f"{exam_title.replace(' ', '_')}_BubbleSheets.zip",
                mime="application/zip"
            )

# ==================== TAB 3 ====================
with tab3:
    st.header("📤 Step 3: Scan & Grade Answers with AI")
    
    if not api_key:
        st.error("🔑 `GEMINI_API_KEY` is missing! Please configure it in your Streamlit Secrets.")
    
    uploaded_files = st.file_uploader("Upload filled student sheets (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files and api_key:
        if st.button("🤖 Grade Sheets with AI"):
            results = []
            progress_bar = st.progress(0)
            
            for idx, file in enumerate(uploaded_files):
                file_bytes = file.read()
                student_name, score = process_omr_with_ai(file_bytes, int(num_questions), answer_key, api_key)
                
                if student_name in ["Unknown Student", "Processing Error", "Auth Error"]:
                    student_name = os.path.splitext(file.name)[0]
                    
                pct = (score / num_questions) * 100
                
                results.append({
                    "Student Name": student_name,
                    "File Name": file.name,
                    "Score": f"{score}/{int(num_questions)}",
                    "Percentage": f"{pct:.1f}%",
                    "Status": "PASS" if pct >= 50 else "FAIL"
                })
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
                
            df_res = pd.DataFrame(results)
            st.dataframe(df_res, use_container_width=True)
            
            excel_buf = io.BytesIO()
            df_res.to_excel(excel_buf, index=False)
            excel_buf.seek(0)
            
            st.download_button(
                label="📊 Download Graded Results (Excel)",
                data=excel_buf,
                file_name="AI_OMR_Graded_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
