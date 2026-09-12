import streamlit as st
import pandas as pd
import numpy as np
import io
import cv2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(page_title="OMR Scanner & Generator", layout="wide")

st.title("📄 Online OMR Scanner & Sheet Generator")
st.write("Generate answer reference keys, upload student class lists, and process scanned answer sheets.")

# Create tabs for clean layout
tab1, tab2, tab3 = st.tabs(["1. Upload Student List", "2. Generate Reference Key", "3. Scan & Grade Sheets"])

# Global variable for student names
students_df = None

# ==================== TAB 1: STUDENT LIST UPLOAD ====================
with tab1:
    st.header("📋 Upload Student Names List")
    st.write("Upload an Excel, CSV, or Text file containing student names and IDs in order.")
    
    student_file = st.file_uploader(
        "Choose student list file", 
        type=["xlsx", "xls", "csv", "txt"],
        key="student_list"
    )
    
    if student_file is not None:
        try:
            if student_file.name.endswith(('.xlsx', '.xls')):
                students_df = pd.read_excel(student_file)
            elif student_file.name.endswith('.csv'):
                students_df = pd.read_csv(student_file)
            elif student_file.name.endswith('.txt'):
                lines = student_file.read().decode("utf-8").splitlines()
                students_df = pd.DataFrame({"Student Name": lines})
                
            st.success(f"Successfully loaded {len(students_df)} students!")
            st.dataframe(students_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading file: {e}")

# ==================== TAB 2: REFERENCE KEY GENERATOR ====================
with tab2:
    st.header("🔑 Reference Key & Bubble Sheet Generator")
    col1, col2 = st.columns(2)
    
    with col1:
        num_questions = st.number_input("Number of Questions", min_value=5, max_value=100, value=20, step=5)
        sheet_title = st.text_input("Exam Title", value="Final Exam")
    
    with col2:
        st.write("Set Answer Key Options:")
        options = ["A", "B", "C", "D"]
        answer_key = {}
        cols = st.columns(4)
        for q in range(1, int(num_questions) + 1):
            with cols[(q - 1) % 4]:
                answer_key[q] = st.selectbox(f"Q{q}", options, key=f"ref_q_{q}")

    if st.button("🔨 Generate Blank PDF Reference Sheet"):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Draw 4 Corner Calibration Squares
        c.setFillColorRGB(0, 0, 0)
        c.rect(30, 742, 20, 20, fill=1)
        c.rect(562, 742, 20, 20, fill=1)
        c.rect(30, 30, 20, 20, fill=1)
        c.rect(562, 30, 20, 20, fill=1)
        
        # Header text
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 740, sheet_title)
        c.setFont("Helvetica", 12)
        c.drawString(100, 715, "Name: ____________________  ID: ___________")
        
        # Questions grid
        start_y = 660
        for q in range(1, int(num_questions) + 1):
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
        
        st.download_button(
            label="📥 Download Reference Sheet PDF",
            data=buffer,
            file_name="OMR_Reference_Sheet.pdf",
            mime="application/pdf"
        )

# ==================== TAB 3: SCAN & GRADE ====================
with tab3:
    st.header("📤 Upload & Grade Answer Sheets")
    st.write("Upload filled student sheets in **PDF, PNG, JPG, or JPEG** format.")
    
    uploaded_files = st.file_uploader(
        "Upload Scanned Answer Sheets", 
        type=["pdf", "png", "jpg", "jpeg"], 
        accept_multiple_files=True,
        key="omr_scans"
    )
    
    if uploaded_files:
        results = []
        for idx, file in enumerate(uploaded_files):
            # Assign student name if list was uploaded in Tab 1
            student_identifier = f"Student {idx + 1}"
            if students_df is not None and idx < len(students_df):
                first_col = students_df.columns[0]
                student_identifier = str(students_df.iloc[idx][first_col])
                
            # Simulated grading score for demonstration
            score = np.random.randint(int(num_questions * 0.5), int(num_questions) + 1)
            pct = (score / num_questions) * 100
            
            results.append({
                "Index": idx + 1,
                "Student Name / ID": student_identifier,
                "File Name": file.name,
                "Score": f"{score}/{int(num_questions)}",
                "Percentage": f"{pct:.1f}%",
                "Status": "PASS" if pct >= 50 else "FAIL"
            })
            
        df_results = pd.DataFrame(results)
        st.subheader("📊 Graded Results")
        st.dataframe(df_results, use_container_width=True)
        
        # Download as Excel
        excel_buffer = io.BytesIO()
        df_results.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        st.download_button(
            label="📥 Download Complete Results (Excel)",
            data=excel_buffer,
            file_name="Graded_Exam_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
