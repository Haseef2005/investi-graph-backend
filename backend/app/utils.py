import re
import logging

# สร้าง Logger
log = logging.getLogger("uvicorn.error")

def is_looks_like_toc(text_snippet: str) -> bool:
    """
    Helper Function: ตรวจสอบว่าข้อความสั้นๆ นี้ดูเหมือนสารบัญหรือไม่
    """
    # 1. เช็กจุดไข่ปลาเยอะๆ (.......)
    if "..." in text_snippet:
        return True
    
    # 2. เช็กคำว่า Page หรือ Pages ตามด้วยตัวเลข
    if re.search(r'Pages?\s+\d+', text_snippet, re.IGNORECASE):
        return True
        
    # 3. เช็กว่าจบด้วยตัวเลขโดดๆ ท้ายบรรทัด (เลขหน้า)
    # เช่น "Risk Factors             15"
    if re.search(r'\s{5,}\d+\s*$', text_snippet):
        return True

    # 4. เช็กว่าเจอ Item ถัดไปเร็วเกินไปไหม (เช่น Item 1 บรรทัดเดียว แล้วเจอ Item 1A เลย)
    if re.search(r'Item\s+1A\.?\s+Risk', text_snippet, re.IGNORECASE):
        return True

    return False

def smart_crop_content(text: str) -> str:
    """
    ฟังก์ชันตัดเนื้อหาอัจฉริยะ ใช้ได้ทั้ง PDF และ Cleaned HTML
    Logic:
    1. หาจุดเริ่มด้วยหลาย Pattern (Priority: 10-K > Annual Report)
    2. ตรวจสอบว่าเป็นสารบัญหรือไม่ (Context Check)
    3. หาจุดจบ
    4. มีระบบกันเหนียว (Fallback)
    """
    
    # --- 1. กำหนด Pattern จุดเริ่ม (เรียงตามความสำคัญ) ---
    start_patterns = [
        r"Item\s+1\.?\s+Business",           # 10-K มาตรฐาน
        r"Business\s+Section",                # บางบริษัทใช้คำนี้
        r"Financial\s+Highlights",            # Annual Report ทั่วไป
        r"Letter\s+to\s+Shareholders",        # Annual Report ทั่วไป
        r"Introduction"                       # กรณีหาอะไรไม่เจอจริงๆ
    ]

    start_index = 0
    found_start = False
    
    for pattern in start_patterns:
        # หาแมตช์ทั้งหมดของ pattern นี้
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        
        for match in matches:
            # ดึงข้อความ 200 ตัวอักษรหลังจากจุดที่เจอ มาตรวจดู
            snippet = text[match.end():match.end()+200]
            
            # ถ้าดูเหมือนสารบัญ -> ข้ามไป (Loop ต่อ)
            if is_looks_like_toc(snippet):
                log.info(f"⏩ Skipping TOC match: '{pattern}' at {match.start()}")
                continue
            
            # ถ้าไม่เหมือนสารบัญ -> นี่แหละจุดเริ่ม!
            start_index = match.start()
            found_start = True
            log.info(f"✅ Found START marker: '{pattern}' at {start_index}")
            break # เจอแล้วหยุดหา match ใน pattern นี้
        
        if found_start:
            break # เจอแล้วหยุดหา pattern อื่นๆ

    if not found_start:
        log.warning("⚠️ Start marker not found. Using full text.")
        start_index = 0

    # --- 2. กำหนด Pattern จุดจบ ---
    end_patterns = [
        r"Item\s+15\.?\s+Exhibits",           # 10-K มาตรฐาน
        r"SIGNATURES",                        # 10-K มาตรฐาน
        r"Form\s+10-K\s+Summary",             # บางทีจบตรงนี้
        r"Appendix",                          # เอกสารทั่วไป
        r"Index\s+to\s+Consolidated"          # งบการเงินท้ายเล่ม
    ]
    
    end_index = len(text)
    
    # ค้นหาจุดจบ (เริ่มหาจาก start_index เป็นต้นไป)
    search_text = text[start_index:]
    
    for pattern in end_patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            # ต้องบวก start_index กลับเข้าไป
            end_index = start_index + match.start()
            log.info(f"✅ Found END marker: '{pattern}' at {end_index}")
            break

    # --- 3. ตัดคำ (Crop) ---
    cropped_text = text[start_index:end_index]

    # --- 4. Validation & Fallback ---
    # ถ้าตัดแล้วเหลือน้อยผิดปกติ (เช่น ต่ำกว่า 1000 ตัวอักษร)
    # แปลว่าเราอาจจะตัดผิด (เช่น จุดเริ่มกับจุดจบอยู่ติดกันเกินไป)
    if len(cropped_text) < 1000:
        log.warning(f"⚠️ Cropped text too short ({len(cropped_text)} chars). Reverting to full text.")
        return text # คืนค่าเดิมดีกว่าข้อมูลหาย

    return cropped_text