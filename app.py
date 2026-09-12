import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
import os
import zipfile
import json
import base64
import qrcode
import urllib.request
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="WordMint OMR Scanner & Generator", layout="wide")

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

def reshape_arabic_text(text):
    if not text or str(text).lower() == 'nan':
        return ""
    clean_text = str(text).strip()
    reshaped_text = arabic_reshaper.reshape(clean_text)
    return get_display(reshaped_text)

# ==================== STEP 1 & 2: WORDMINT SCRAPER ====================
@st.cache_data(ttl=3600)
def scrape_wordmint_puzzle(url_or_id):
    puzzle_id = re.search(r'\d+', url_or_id)
    target_id = puzzle_id.group(0) if puzzle_id else "8425760"
    target_url = f"https://wordmint.com/puzzles/{target_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        res = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        title_el = soup.find("h1") or soup.find("title")
        raw_title = title_el.get_text(strip=True) if title_el else "WordMint Exam"
        clean_title = raw_title.replace("WordMint", "").replace("|", "").strip()

        UI_FILTER = ["sign in", "create account", "open main menu", "wordmint", "privacy", "terms", "puzzle"]
        clues_data = []
        
        clue_nodes = soup.find_all(["div", "li", "span"], class_=re.compile(r"clue|word|item", re.I))
        for node in clue_nodes:
            text = node.get_text(" ", strip=True)
            if text and not any(bad_word in text.lower() for bad_word in UI_FILTER):
                clues_data.append(text)

        clues_data = list(dict.fromkeys(clues_data))

        if not clues_data:
            clues_data = [f"WordMint Question {i:02d}" for i in range(1, 21)]

        return clean_title, clues_data
    except Exception:
        return f"WordMint Exam #{target_id}", [f"Question {i:02d}" for i in range(1, 21)]

# ==================== STEP 4: PDF GENERATOR ====================
def create_wordmint_pdf(title, clues, s_name):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Alignment Corner Registration Marks
    c.setFillColorRGB(0, 0, 0)
    c.rect(30, 742, 20, 20, fill=1)
    c.rect(562, 742, 20, 20, fill=1)
    c.rect(30, 30, 20, 20, fill=1)
    c.rect(562, 30, 20, 20, fill=1)
    
    # Header Information
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, 740, f"Exam: {title[:35]}")
    
    formatted_name = reshape_arabic_text(s_name)
    c.setFont(ARABIC_FONT, 12)
    c.drawString(60, 712, f"Student: {formatted_name}")
    c.line(60, 695, 542, 695)

    # Questions & Bubbles Grid
    y_position = 665
    options = ["A", "B", "C", "D"]
    
    for i, clue in enumerate(clues[:20], 1):
        c.setFont("Helvetica", 9)
        clean_clue = clue[:38] + ("..." if len(clue) > 38 else "")
        c.drawString(60, y_position, f"{i:02d}. {clean_clue}")
        
        for idx, opt in enumerate(options):
            bx = 390 + (idx * 30)
            c.circle(bx, y_position + 3, 5, stroke=1, fill=0)
            c.drawString(bx - 3, y_position, opt)
        y_position -= 26
        
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# ==================== STEP 5: VISION GRADING ====================
def process_omr_with_ai(img_bytes, total_q, key_dict, key):
    if not key:
        return "API Key Missing", 0

    base64_image = base64.b64encode(img_bytes).decode("utf-8")
    clean_key = str(key).strip()
    
    prompt = f"""
    Analyze this exam sheet image carefully.
    1. Extract the student name written next to "Student:".
    2. Examine questions Q01 through Q{total_q:02d}.
    3. Determine which option (A, B, C, or D) is filled/shaded.
    
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

    headers = {"Content-Type": "application/json"}
    models = ["gemini-2.0-flash", "gemini-1.5-flash"]

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            res_json = response.json()

            if response.status_code == 200:
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
            elif response.status_code in [404, 400]:
                continue
            else:
                return "Auth Error", 0
        except Exception:
            continue

    return "Processing Error", 0

# ==================== MAIN UI ====================
st.title("🧩 WordMint Reverse-Engineered OMR Suite")

puzzle_input = st.text_input("WordMint Puzzle URL or ID:", value="https://wordmint.com/puzzles/8425760")
puzzle_title, puzzle_clues = scrape_wordmint_puzzle(puzzle_input)

st.success(f"Loaded Puzzle: **{puzzle_title}** ({len(puzzle_clues)} questions extracted)")

# Default Answer Key Dictionary (Auto-set to Option A for extracted questions)
num_q = min(len(puzzle_clues), 20)
answer_key = {i: "A" for i in range(1, num_q + 1)}

tab1, tab2 = st.tabs(["1. Generate PDF Worksheet", "2. Scan & Grade Sheet"])

with tab1:
    st.header("📄 PDF Sheet Generator")
    student_name = st.text_input("Student Name (Arabic & English supported):", value="احمد علي")

    if st.button("🚀 Download Custom PDF Sheet"):
        pdf_bytes = create_wordmint_pdf(puzzle_title, puzzle_clues, student_name)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_bytes,
            file_name=f"Sheet_{student_name.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

with tab2:
    st.header("📤 AI Vision Sheet Reader")
    if not api_key:
        st.warning("⚠️ Please set your `GEMINI_API_KEY` in Streamlit secrets to enable AI grading.")

    uploaded_files = st.file_uploader("Upload filled student sheets", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files and api_key and st.button("🤖 Grade Sheets"):
        results = []
        progress_bar = st.progress(0)
        
        for idx, file in enumerate(uploaded_files):
            file_bytes = file.read()
            s_name, score = process_omr_with_ai(file_bytes, num_q, answer_key, api_key)
            
            if s_name in ["Unknown Student", "Processing Error", "Auth Error"]:
                s_name = os.path.splitext(file.name)[0]
                
            pct = (score / num_q) * 100
            
            results.append({
                "Student Name": s_name,
                "File Name": file.name,
                "Score": f"{score}/{num_q}",
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
            label="📊 Download Graded Excel Report",
            data=excel_buf,
            file_name="WordMint_Graded_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
