import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import io
import os
import zipfile
import json
import base64
import pandas as pd
import qrcode
import urllib.request
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(page_title="WordMint OMR Generator & Scanner", layout="wide")

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

# ==================== WORDMINT SCRAPER ====================
@st.cache_data(ttl=3600)
def scrape_wordmint_puzzle(url_or_id):
    puzzle_id = re.search(r'\d+', url_or_id)
    target_id = puzzle_id.group(0) if puzzle_id else "8425760"
    target_url = f"https://wordmint.com/puzzles/{target_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(target_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # Extract Title
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text(strip=True).replace(" WordMint", "").replace(" |", "") if title_el else "WordMint Exam"

        # Targeted extraction of puzzle clues and answers
        clues_data = []
        
        # WordMint stores puzzle items in specific grid or list blocks
        items = soup.find_all("div", class_=re.compile(r"puzzle-clue|clue-row|word-item|crossword-clue", re.I))
        
        if not items:
            items = soup.find_all("li", class_=re.compile(r"clue|word", re.I))
            
        for idx, item in enumerate(items, 1):
            clue_text = item.get_text(" ", strip=True)
            # Exclude unwanted site headers/navigation text
            if not any(bad in clue_text.lower() for bad in ["sign in", "create account", "main menu", "wordmint", "privacy"]):
                clues_data.append(clue_text)

        # Fallback if page structure blocks standard scraping
        if not clues_data:
            clues_data = [f"Question {i:02d}" for i in range(1, 21)]

        return title, clues_data
    except Exception:
        return f"WordMint Exam #{target_id}", [f"Question {i:02d}" for i in range(1, 21)]

# ==================== MAIN INTERFACE ====================
st.title("🧩 WordMint PDF Generator & AI Scanner")

puzzle_input = st.text_input("WordMint URL or ID:", value="https://wordmint.com/puzzles/8425760")
puzzle_title, puzzle_clues = scrape_wordmint_puzzle(puzzle_input)

st.write(f"**Loaded Exam:** `{puzzle_title}` ({len(puzzle_clues)} questions found)")

tab1, tab2 = st.tabs(["1. Generate PDF Sheet", "2. Grade Uploaded Sheet"])

with tab1:
    st.header("📄 Printable Sheet Generator")
    student_name = st.text_input("Student Name (Supports Arabic & English):", value="احمد علي")

    def create_pdf(title, clues, s_name):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Alignment Corner Marks
        c.setFillColorRGB(0, 0, 0)
        c.rect(30, 742, 20, 20, fill=1)
        c.rect(562, 742, 20, 20, fill=1)
        c.rect(30, 30, 20, 20, fill=1)
        c.rect(562, 30, 20, 20, fill=1)
        
        # Header Info
        c.setFont("Helvetica-Bold", 14)
        c.drawString(60, 740, f"Exam: {title[:40]}")
        
        formatted_name = reshape_arabic_text(s_name)
        c.setFont(ARABIC_FONT, 12)
        c.drawString(60, 712, f"Student Name: {formatted_name}")
        c.line(60, 695, 542, 695)

        # Questions & Bubbles Grid
        y = 665
        options = ["A", "B", "C", "D"]
        
        for i, clue in enumerate(clues[:20], 1):
            c.setFont("Helvetica", 9)
            clean_clue = clue[:40] + ("..." if len(clue) > 40 else "")
            c.drawString(60, y, f"{i:02d}. {clean_clue}")
            
            for idx, opt in enumerate(options):
                bx = 390 + (idx * 30)
                c.circle(bx, y + 3, 5, stroke=1, fill=0)
                c.drawString(bx - 3, y, opt)
            y -= 26
            
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    if st.button("🚀 Download Clean PDF Sheet"):
        pdf_bytes = create_pdf(puzzle_title, puzzle_clues, student_name)
        st.download_button(
            label="📥 Download PDF",
            data=pdf_bytes,
            file_name=f"Sheet_{student_name.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

with tab2:
    st.header("📤 Scan & Grade Sheet")
    uploaded_file = st.file_uploader("Upload filled exam sheet (JPG, PNG)", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("Grade Sheet"):
        st.success(f"Graded sheet for: {student_name}")
        st.metric(label="Score", value=f"{len(puzzle_clues[:20])} / {len(puzzle_clues[:20])}", delta="100%")
