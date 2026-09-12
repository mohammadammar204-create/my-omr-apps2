# ==================== HELPER FUNCTIONS ====================
def load_student_dataframe(uploaded_file):
    if uploaded_file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.txt'):
        lines = uploaded_file.read().decode("utf-8").splitlines()
        df = pd.DataFrame({"Student Name": lines})
    
    # Auto-detect column containing names or fall back to the first text column
    name_col = None
    for col in df.columns:
        if any(keyword in str(col).lower() for keyword in ['name', 'اسم', 'طالب', 'student']):
            name_col = col
            break
            
    if name_col is None:
        name_col = df.columns[0]  # Take the very first column
        
    # Rename selected column to 'Student Name'
    df = df.rename(columns={name_col: "Student Name"})
    return df

def reshape_arabic_text(text):
    if not text or str(text).lower() == 'nan':
        return ""
    # Ensure raw string conversion
    clean_text = str(text).strip()
    reshaped_text = arabic_reshaper.reshape(clean_text)
    return get_display(reshaped_text)
