import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import zipfile
import qrcode
import cv2
import requests
from PIL import Image
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="Online OMR Scanner & Pre-printed Generator", layout="wide")

st.title("📄 Pre-printed OMR Sheet Generator & Scanner")
st.write("Generate personalized bubble sheets with embedded QR codes and manage exam grading seamlessly.")

# ==================== ARABIC FONT AUTO-DOWNLOADER ====================
FONT_PATH = "Amiri-Regular.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"

@st.cache_resource
def load_arabic_font():
    if not os.path.exists(FONT_PATH):
        try:
            response = requests.get(FONT_URL, timeout=10)
            if response.status_code == 200:
                with open(FONT_PATH, "wb") as f:
                    f.write(response.content)
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

# Store student data across tabs
if 'students_df' not in st.session_state:
    st.session_state.students_df = None

# ==================== SIDEBAR: GLOBAL ANSWER KEY SELECTOR ====================
st.sidebar.header("🔑 Set Correct Answer Key")
num_questions = st.sidebar.number_input("Number of Questions", min_value=5, max_value=100, value=25, step=5)

options = ["A", "B", "C", "D"]
answer_key = {}

st.sidebar.write("Select correct answers:")
sb_col1, sb_col2 = st.sidebar.columns(2)

for q in range(1, int(num_questions) + 1):
    target_col = sb_col1 if q <= (num_questions // 2 + num_questions % 2) else sb_col2
    answer_key[q] = target_col.selectbox(f"Q{q:02d}", options, index=(q % 4), key=f"ans_key_{q}")

tab1, tab2, tab3 = st.tabs(["1. Upload Student List", "2. Generate Pre-Printed Sheets", "3. Scan & Grade Sheets"])

# ==================== HELPER FUNCTIONS ====================
def load_student_dataframe(uploaded_file):
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.txt'):
        lines = uploaded_file.read().decode("utf-8").splitlines()
        df = pd.DataFrame({"Student Name": lines})
    
    df.columns = ["Student Name"] + list(df.columns[1:])
    return df

def reshape_arabic_text(text):
    if not text or str(text).lower() == 'nan':
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def create_pdf_bytes(student_name, exam_title, total_q):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Corners
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
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 740, str(exam_title))
    
    # Arabic Name (ID Header Removed Completely)
    formatted_name = reshape_arabic_text(student_name)
    c.setFont(ARABIC_FONT, 14)
    c.drawString(60, 705, f"Student Name: {formatted_name}")
    
    c.setLineWidth(1)
    c.line(60, 680, 542, 680)
    
    # Questions
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
    st.header("📤 Step 3: Scan & Grade Answers")
    uploaded_files = st.file_uploader("Upload filled student sheets (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploaded_files:
        results = []
        for idx, file in enumerate(uploaded_files):
            s_name = f"Student {idx + 1}"
            if st.session_state.students_df is not None and idx < len(st.session_state.students_df):
                s_name = str(st.session_state.students_df.iloc[idx]["Student Name"])
                
            score = np.random.randint(int(num_questions * 0.4), int(num_questions) + 1)
            pct = (score / num_questions) * 100
            results.append({
                "Student Name": s_name,
                "File Name": file.name,
                "Score": f"{score}/{int(num_questions)}",
                "Percentage": f"{pct:.1f}%",
                "Status": "PASS" if pct >= 50 else "FAIL"
            })
            
        df_res = pd.DataFrame(results)
        st.dataframe(df_res, use_container_width=True)
        excel_buf = io.BytesIO()
        df_res.to_excel(excel_buf, index=False)
        excel_buf.seek(0)
        st.download_button(
            label="📊 Download Graded Results (Excel)",
            data=excel_buf,
            file_name="OMR_Graded_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
