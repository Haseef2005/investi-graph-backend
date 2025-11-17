# app/processing.py
import logging
import os
import aiofiles
from pypdf import PdfReader

# "Import" ตัว "หั่น" (Chunking) และ "แปลง" (Embedding)
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import models, crud
from app.database import SessionLocal # <-- "Import" Session

UPLOAD_DIRECTORY = "/app/uploads"
log = logging.getLogger("uvicorn.error")

# --- "โหลด" AI (แค่ครั้งเดียว) ---
# (นี่คือ Model ที่ "เล็ก" และ "เร็ว" ... 384 มิติ)
log.info("Loading SentenceTransformer model...")
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
log.info("Model loaded.")
# ---------------------------------


# "สร้าง" ตัว "หั่น" (เราจะหั่นทีละ 1000 ตัวอักษร)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200, # (ให้มัน "เหลื่อม" กัน 200)
    length_function=len,
)


async def save_extract_chunk_and_embed(
    document_id: int,
    filename: str,
    content_type: str,
    content: bytes
):
    """
    "รื้อ" ฟังก์ชันนี้ใหม่หมด:
    1. "เซฟ" ไฟล์ (ชั่วคราว)
    2. "สกัด" Text
    3. "หั่น" (Chunk) Text
    4. "แปลง" (Embed) Text
    5. "บันทึก" Chunks + Vectors ลง DB
    """

    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{document_id}_{filename}")

    log.info(f"--- 🤖 TASK START (Doc ID: {document_id}) ---")

    try:
        # 1. "เซฟ" ไฟล์ (ชั่วคราว)
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)

        log.info(f"File saved. Extracting text...")

        # 2. "สกัด" Text
        extracted_text = ""
        if content_type == "application/pdf":
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
        else:
            extracted_text = content.decode("utf-8")

        log.info(f"Text extracted. (Length: {len(extracted_text)})")

        # 3. "หั่น" (Chunk) Text
        log.info(f"Chunking text...")
        chunks = text_splitter.split_text(extracted_text)
        log.info(f"Text chunked into {len(chunks)} pieces.")

        # 4. "แปลง" (Embed) Text (นี่คือส่วนที่ "หนัก" ที่สุด)
        log.info(f"Embedding chunks...")
        # (เรา "แปลง" ทั้งหมด... ทีเดียว)
        embeddings = EMBEDDING_MODEL.encode(chunks)
        log.info(f"Embeddings created.")

        # 5. "บันทึก" Chunks + Vectors ลง DB
        # (เราต้อง "สร้าง" DB Session "ใหม่" ...
        #  ...เพราะ Task นี้ "อิสระ" จาก API)

        # (เราจะ "สร้าง" List ของ "วัตถุดิบ" (Objects)
        db_chunks = []
        for i in range(len(chunks)):
            db_chunks.append(
                models.Chunk(
                    text=chunks[i],
                    embedding=embeddings[i], # <-- "Vector"
                    document_id=document_id
                )
            )

        # "เชื่อมต่อ" DB (แบบ "ชั่วคราว")
        async with SessionLocal() as db:
            log.info(f"Saving {len(db_chunks)} chunks to DB...")
            # "ยัด" (Bulk Save) ทั้งหมดทีเดียว
            db.add_all(db_chunks)
            await db.commit() # <-- "บันทึก"

        log.info(f"--- 🤖 TASK DONE (Doc ID: {document_id}) ---")

    except Exception as e:
        log.error(f"Error processing file {file_path}: {e}", exc_info=True)
        log.error(f"--- 🤖 TASK FAILED (Doc ID: {document_id}) ---")

    finally:
        # "ลบ" ไฟล์ PDF/TXT ชั่วคราว (ที่เราเซฟไว้) ทิ้ง
        if os.path.exists(file_path):
            os.remove(file_path)
        log.info(f"Cleaned up {file_path}")