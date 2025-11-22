import os
import shutil
import glob
from sec_edgar_downloader import Downloader
from bs4 import BeautifulSoup
from app.config import settings
from app import processing, crud, models
from app.database import SessionLocal
import logging
import re
from app.utils import smart_crop_content

log = logging.getLogger("uvicorn.error")

TEMP_SEC_DIR = "/app/temp_sec" # โฟลเดอร์ชั่วคราวสำหรับพักไฟล์

def clean_html_content(raw_content: str) -> str:
    """
    1. Extract only the '10-K' document section from the full submission.
    2. Remove HTML tags.
    3. Clean up whitespace.
    """
    if not raw_content:
        return ""

    # --- Step 1: หา Document ที่เป็นเนื้อหาหลัก (10-K, 10-Q, 20-F) ---
    # Pattern: หา <DOCUMENT> ที่ข้างในมี <TYPE>10-K... แล้วดึง <TEXT> ออกมา
    # (?s) คือให้ . match newlines ได้
    
    # ลองหา 10-K หรือ 10-Q หรือ 20-F
    doc_match = re.search(
        r'<DOCUMENT>\s*<TYPE>(?:10-K|10-Q|20-F).*?<TEXT>(.*?)</TEXT>\s*</DOCUMENT>', 
        raw_content, 
        re.IGNORECASE | re.DOTALL
    )
    
    if doc_match:
        # ถ้าเจอ: เอาเฉพาะส่วนที่เป็น HTML ของรายงานมาใช้ (ทิ้งขยะรูปภาพไปเลย)
        html_content = doc_match.group(1)
    else:
        # ถ้าไม่เจอ pattern (เผื่อไฟล์ format แปลก): ใช้ทั้งหมด แต่ต้องระวัง
        # แนะนำให้ลองหา tag <TEXT> แรกสุดแทน เพราะมักจะเป็นรายงานหลัก
        text_match = re.search(r'<TEXT>(.*?)</TEXT>', raw_content, re.IGNORECASE | re.DOTALL)
        if text_match:
            html_content = text_match.group(1)
        else:
            html_content = raw_content # จนปัญญา ใช้ของเดิม

    # --- Step 2: BeautifulSoup Cleaning (เหมือนเดิม) ---
    soup = BeautifulSoup(html_content, "html.parser")
    
    # ลบ Tag ขยะ (Script, Style, และ Table ที่ซ่อนไว้)
    for element in soup(["script", "style", "head", "meta", "link", "noscript"]):
        element.decompose()
        
    # (Optional) ลบข้อมูลที่เป็น Base64/Binary ยาวๆ ที่อาจหลุดรอดมา
    # (เช่น ถ้ามันไม่อยู่ใน tag graphic แต่อยู่ใน div)
    # แต่ปกติ Step 1 จะกันได้ 99% แล้วครับ

    # --- Step 3: Extract Text ---
    text = soup.get_text(separator=" ", strip=True)
    # ลบคำพวก us-gaap:AbcdefMember ออกไปเลย
    text = re.sub(r'\b[a-z0-9]+:[A-Za-z0-9_]+Member\b', '', text)
    text = re.sub(r'\b[a-z0-9]+:[A-Za-z0-9_]+\b', '', text)
    
    # การตัดหน้าปกและสารบัญ ---
    text = smart_crop_content(text)
    # ลบ Whitespace ซ้ำซ้อน
    text = " ".join(text.split())
    
    return text

async def fetch_and_process_10k(user_id: int, ticker: str, amount: int = 1):
    ticker = ticker.upper()
    log.info(f"🔍 Fetching 10-K for {ticker}...")

    company_dir = os.path.join(TEMP_SEC_DIR, "sec-edgar-filings", ticker)

    if os.path.exists(company_dir):
        log.info(f"🧹 Cleaning up old data for {ticker}...")
        shutil.rmtree(company_dir)

    dl = Downloader("Investi-Graph", settings.SEC_API_EMAIL, TEMP_SEC_DIR)

    try:
        dl.get("10-K", ticker, limit=amount)
        
        search_path = os.path.join(TEMP_SEC_DIR, "sec-edgar-filings", ticker, "10-K", "*", "*.txt")
        files = glob.glob(search_path)
        
        if not files:
            log.error(f"No 10-K found for {ticker}")
            return
        
        files.sort(reverse=True)

        file_path = files[0]
        log.info(f"📂 Found file: {file_path}")

        # 3. อ่านไฟล์
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content = f.read()
            
        # --- 4. Clean HTML ก่อนใช้งาน ---
        log.info("🧹 Cleaning HTML content...")
        clean_text = clean_html_content(raw_content)
        clean_text = smart_crop_content(clean_text)
        log.info(f"Cleaned text length: {len(clean_text)}")
        
        # แปลงเป็น bytes
        content_bytes = clean_text.encode("utf-8")
        filename = f"{ticker}_10K_Report.txt"

        # 5. ส่งต่อให้ Pipeline (เหมือนเดิม)
        async with SessionLocal() as db:
            db_doc = await crud.create_document(db=db, filename=filename, owner_id=user_id)
            
            await processing.save_extract_chunk_and_embed(
                document_id=db_doc.id,
                filename=filename,
                content_type="text/plain", # ตอนนี้เป็น Text ล้วนแล้ว
                content=content_bytes
            )

        log.info(f"✅ SEC Fetch & Process Complete for {ticker}")

    except Exception as e:
        log.error(f"❌ Error fetching SEC data: {e}")
    
    finally:
        if os.path.exists(os.path.join(TEMP_SEC_DIR, "sec-edgar-filings", ticker)):
             shutil.rmtree(os.path.join(TEMP_SEC_DIR, "sec-edgar-filings", ticker))