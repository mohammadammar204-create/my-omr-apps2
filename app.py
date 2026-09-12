from reportlab.lib.utils import ImageReader

# ==================== HELPER FUNCTION: CREATE PRE-PRINTED PDF ====================
def create_pdf_bytes(student_name, student_id, exam_title, total_q):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Corner Anchors
    c.setFillColorRGB(0, 0, 0)
    c.rect(30, 742, 20, 20, fill=1)
    c.rect(562, 742, 20, 20, fill=1)
    c.rect(30, 30, 20, 20, fill=1)
    c.rect(562, 30, 20, 20, fill=1)
    
    # Generate QR Code safely using PIL Image
    qr = qrcode.make(f"{student_id}:{student_name}")
    qr_pil = qr.get_image() # Get PIL image instance
    qr_reader = ImageReader(qr_pil) # Wrap in ReportLab ImageReader
    
    c.drawImage(qr_reader, 470, 665, width=75, height=75)
    
    # Student Info
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 740, exam_title)
    
    c.setFont("Helvetica", 12)
    c.drawString(60, 710, f"Student Name: {student_name}")
    c.drawString(60, 690, f"Student ID: {student_id}")
    
    c.setLineWidth(1)
    c.line(60, 675, 542, 675)
    
    # Questions grid
    start_y = 640
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
