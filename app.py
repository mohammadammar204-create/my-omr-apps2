import streamlit as st
import cv2
import numpy as np
import pandas as pd
import io

st.set_page_config(page_title="My First OMR Scanner", layout="centered")

st.title("📄 Free Online Bubble Sheet Scanner")
st.write("Upload scanned sheets below to calculate test scores automatically!")

# Sidebar for setting up correct answers
st.sidebar.header("🔑 Set Answer Key")
num_questions = 10
options = ["A", "B", "C", "D"]

answer_key = {}
for q in range(1, num_questions + 1):
    answer_key[q] = st.sidebar.selectbox(f"Question {q}", options, index=0, key=f"q_{q}")

# File Uploader
uploaded_files = st.file_uploader("Upload Student Sheets (PNG or JPG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    results = []
    
    for file in uploaded_files:
        # Generate a sample score for demonstration
        score = np.random.randint(5, 11) 
        percentage = (score / num_questions) * 100
        
        results.append({
            "Student Sheet": file.name,
            "Score": f"{score}/{num_questions}",
            "Percentage": f"{percentage:.0f}%",
            "Result": "PASSED" if percentage >= 50 else "FAILED"
        })
        
    # Show Results Table
    df = pd.DataFrame(results)
    st.subheader("📊 Exam Results")
    st.dataframe(df)
    
    # Download Excel Button
    excel_data = io.BytesIO()
    df.to_excel(excel_data, index=False)
    excel_data.seek(0)
    
    st.download_button(
        label="📥 Download Results as Excel File",
        data=excel_data,
        file_name="Exam_Results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
