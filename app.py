import arabic_reshaper
from bidi.algorithm import get_display

def reshape_arabic_text(text):
    """Reshapes and reverses Arabic text for proper PDF rendering."""
    if not text or str(text).lower() == 'nan':
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def create_pdf_bytes(student_name, student_id, exam_title, total_q):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # 1. Corner Calibration Anchors
    c.setFillColorRGB(0, 0, 0)
    c.rect(30, 742, 20, 20, fill=1)
    c.rect(562, 742, 20, 20, fill=1)
    c.rect(30, 30, 20, 20, fill=1)
    c.rect(562, 30, 20, 20, fill=1)
    
    # 2. Generate QR Code containing Student Data
    qr = qrcode.make(f"{student_id}:{student_name}")
    qr_pil = qr.get_image()
    qr_reader = ImageReader(qr_pil)
    c.drawImage(qr_reader, 470, 665, width=75, height=75)
    
    # 3. Exam Title & Clean Arabic Student Name (ID Removed)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 740, str(exam_title))
    
    formatted_name = reshape_arabic_text(student_name)
    c.setFont("Helvetica", 12)
    c.drawString(60, 705, f"Student Name: {formatted_name}")
    
    c.setLineWidth(1)
    c.line(60, 680, 542, 680)
    
    # 4. Bubble Grid Questions
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
