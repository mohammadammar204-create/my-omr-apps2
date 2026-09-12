def process_omr_with_ai(img_bytes, total_q, key_dict, key):
    if not key:
        return "API Key Missing", 0

    base64_image = base64.b64encode(img_bytes).decode("utf-8")
    
    # Pass key as a URL parameter to support standard Google AI Studio authentication
    clean_key = key.strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={clean_key}"
    
    headers = {
        "Content-Type": "application/json"
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
