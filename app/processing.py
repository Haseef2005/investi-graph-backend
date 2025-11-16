# app/processing.py
import logging
import os
import aiofiles # <-- Library สำหรับ "เขียน" ไฟล์แบบ Async
from fastapi import UploadFile
from pypdf import PdfReader # <-- Library อ่าน PDF

# (สร้าง "ที่เก็บ" ไฟล์ชั่วคราว)
# (ในโลกจริง... เราจะใช้ S3... แต่ตอนนี้ "เก็บใน Docker" ไปก่อน)
UPLOAD_DIRECTORY = "/app/uploads"

log = logging.getLogger("uvicorn.error")


async def save_and_extract_text(
    document_id: int,
    filename: str,      # <-- "แก้" (1/2) รับตัวแปรใหม่
    content_type: str,  # <-- "แก้" (1/2) รับตัวแปรใหม่
    content: bytes      # <-- "แก้" (1/2) รับตัวแปรใหม่
) -> str:
    """
    1. "เซฟ" ไฟล์ลง Disk (ใน Docker)
    2. "สกัด" (Extract) Text
    """

    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{document_id}_{filename}")

    log.info(f"--- 🤖 TASK START ---")
    log.info(f"Saving file to: {file_path}")

    try:
        # 1. "เซฟ" ไฟล์ (จาก "เนื้อใน" ที่เรามี)
        async with aiofiles.open(file_path, "wb") as out_file:
            # "ลบ" await file.read() ทิ้ง
            await out_file.write(content) # <-- "แก้" (2/2) เขียน "เนื้อใน"

        log.info(f"File saved. Extracting text...")

        # 2. "สกัด" Text
        extracted_text = ""

        if content_type == "application/pdf": # <-- "แก้" (2/2)
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
        else:
            extracted_text = content.decode("utf-8")

        log.info(f"Text extracted. (Length: {len(extracted_text)})")
        log.info(f"--- 🤖 TASK DONE ---")

        return extracted_text

    except Exception as e:
        log.error(f"Error processing file {file_path}: {e}", exc_info=True) # (เพิ่ม exc_info=True เพื่อ Debug ง่ายขึ้น)
        log.error(f"--- 🤖 TASK FAILED ---")
        return None # <-- คืนค่า None ถ้าพัง