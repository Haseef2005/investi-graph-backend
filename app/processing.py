import asyncio
import logging
import os
import aiofiles
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer, CrossEncoder
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app import models, crud
from app.database import SessionLocal
from app.config import settings
import sqlalchemy as sa
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed
from app import knowledge_graph
import re
from app.utils import smart_crop_content

UPLOAD_DIRECTORY = "/app/uploads"
log = logging.getLogger("uvicorn.error")

# --- 1. Load Models ---
log.info("Loading Embedding Model (Bi-Encoder)...")
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

log.info("Loading Reranker Model (Cross-Encoder)...")
# ใช้รุ่น ms-marco-MiniLM-L-6-v2 (เล็ก เร็ว แม่น)
RERANKER_MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2") 
log.info("Models loaded.")
# ----------------------

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)

async def save_extract_chunk_and_embed(
    document_id: int,
    filename: str,
    content_type: str,
    content: bytes
):
    # ... (ฟังก์ชันนี้เหมือนเดิม 100% ไม่ต้องแก้) ...
    # (พี่ขอละไว้เพื่อความสั้นนะครับ แต่น้อง Copy ของเดิมมาแปะได้เลย หรือถ้าจะ Copy ทับ ให้บอกพี่ เดี๋ยวพี่แปะตัวเต็มให้)
    # ... (Logic เดิม: Save File -> Extract -> Chunk -> Embed -> Save DB -> Graph Extract) ...
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{document_id}_{filename}")

    log.info(f"--- 🤖 TASK START (Doc ID: {document_id}) ---")

    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)
        
        extracted_text = ""
        if content_type == "application/pdf":
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
            log.info("✂️ Cropping PDF content...")
            extracted_text = smart_crop_content(extracted_text)
        else:
            extracted_text = content.decode("utf-8")

        chunks = text_splitter.split_text(extracted_text)
        
        # RAG Embed
        embeddings = EMBEDDING_MODEL.encode(chunks)
        db_chunks = []
        for i in range(len(chunks)):
            db_chunks.append(
                models.Chunk(text=chunks[i], embedding=embeddings[i], document_id=document_id)
            )

        async with SessionLocal() as db:
            db.add_all(db_chunks)
            await db.commit()
        
        # Graph Extract (Limit 5)
        MAX_GRAPH_CHUNKS = 5
        for i, chunk in enumerate(chunks):
            if i >= MAX_GRAPH_CHUNKS: break
            log.info(f"🧠 Processing chunk {i+1}/{min(MAX_GRAPH_CHUNKS, len(chunks))} for graph extraction...")
            graph_data = await knowledge_graph.extract_graph_from_text(chunk)
            await knowledge_graph.store_graph_data(document_id, graph_data)
            # Small delay only for API courtesy (retries handle rate limits)
            if i < MAX_GRAPH_CHUNKS - 1:  # Don't sleep after the last chunk
                log.info("⏳ Sleeping 2s for API courtesy...")
                await asyncio.sleep(2)

        log.info(f"--- 🤖 TASK DONE (Doc ID: {document_id}) ---")

    except Exception as e:
        log.error(f"Error processing: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)


# --- Reranking Helper Function ---
def rerank_chunks(query: str, chunks: list[models.Chunk], top_k: int = 5) -> list[models.Chunk]:
    """
    รับ Chunks จำนวนมาก -> ใช้ CrossEncoder ให้คะแนนเทียบกับ Query -> คืนค่า Top K
    """
    if not chunks:
        return []
    
    # เตรียมข้อมูลคู่ (Query, Document Text)
    pairs = [[query, chunk.text] for chunk in chunks]
    
    # ให้คะแนน (Scores)
    scores = RERANKER_MODEL.predict(pairs)
    
    # จับคู่ Chunk กับ Score
    chunk_score_pairs = list(zip(chunks, scores))
    
    # เรียงลำดับจากคะแนนมากไปน้อย
    sorted_pairs = sorted(chunk_score_pairs, key=lambda x: x[1], reverse=True)
    
    # ตัดเอาเฉพาะ Top K
    top_chunks = [pair[0] for pair in sorted_pairs[:top_k]]
    
    log.info(f"Reranking done. Reduced {len(chunks)} -> {len(top_chunks)}")
    return top_chunks


# Retrieval (Global) - With Reranking
async def retrieve_relevant_chunks_global(user_id: int, query_text: str) -> list[models.Chunk]:
    log.info(f"Retrieving global (Stage 1: Vector Search)...")
    query_embedding = EMBEDDING_MODEL.encode(query_text)
    
    async with SessionLocal() as db:
        stmt = (
            sa.select(models.Chunk)
            .join(models.Document)
            .where(models.Document.owner_id == user_id)
            .order_by(models.Chunk.embedding.l2_distance(query_embedding))
            .limit(20) # <--- ดึงมาเยอะๆ ก่อน (20)
        )
        result = await db.execute(stmt)
        initial_chunks = result.scalars().all()
        
    # Stage 2: Reranking
    return rerank_chunks(query_text, initial_chunks, top_k=5) # คัดเหลือ 5


# Retrieval (Single Doc) - With Reranking
async def retrieve_relevant_chunks(document_id: int, query_text: str) -> list[models.Chunk]:
    log.info(f"Retrieving single doc (Stage 1: Vector Search)...")
    query_embedding = EMBEDDING_MODEL.encode(query_text)

    async with SessionLocal() as db:
        stmt = (
            sa.select(models.Chunk)
            .where(models.Chunk.document_id == document_id)
            .order_by(models.Chunk.embedding.l2_distance(query_embedding))
            .limit(20) # <--- ดึงมาเยอะๆ ก่อน (20)
        )
        result = await db.execute(stmt)
        initial_chunks = result.scalars().all()

    # Stage 2: Reranking
    return rerank_chunks(query_text, initial_chunks, top_k=5) # คัดเหลือ 5


# generate_answer
async def generate_answer(
    query: str, 
    context_chunks: list[models.Chunk],
    doc_id: int = None, # รับ doc_id มาด้วย (ถ้ามี)
    user_id: int = None # หรือ user_id (สำหรับ global)
) -> str:
    
    # 1. เตรียม Vector Context (Text Chunks)
    vector_context = "\n\n".join([chunk.text for chunk in context_chunks])
    
    # 2. หา Graph Context (เรียกฟังก์ชันใหม่ที่เราเพิ่งเขียน)
    log.info("Fetching GraphRAG context...")
    try:
        # ถ้ามี doc_id ให้หาเฉพาะใน doc นั้น, ถ้าไม่มีให้หาแบบ Global (แต่ต้องระวังเรื่อง Permission ในอนาคต)
        # ในที่นี้เอาแบบง่ายก่อน คือถ้าเป็น Global Chat (doc_id=None) เราค้นทั้งกราฟเลย
        # หรือน้องจะส่ง user_id ไปกรองใน Knowledge Graph ก็ได้ (Task Advance)
        graph_context = await knowledge_graph.query_graph_context(query, doc_id)
    except Exception as e:
        log.error(f"GraphRAG failed: {e}")
        graph_context = ""

    log.info(f"Generating answer using {len(context_chunks)} chunks + Graph Context.")

    # 3. รวม Prompt
    prompt = f"""
    You are an expert financial analyst AI.
    Answer the user's question based on the context provided below.
    
    The context consists of:
    1. "Document Excerpts": Text retrieved from the document files.
    2. "Knowledge Graph": Relationships extracted from the data.

    Combine both sources to give a comprehensive answer.
    If the answer is not found, say so.

    --- DOCUMENT EXCERPTS ---
    {vector_context}
    
    --- KNOWLEDGE GRAPH ---
    {graph_context}
    ---

    QUESTION:
    {query}
    """

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def call_llm_api():
        return await acompletion(
            model=f"{settings.LLM_PROVIDER}/llama-3.1-8b-instant",
            api_key=settings.LLM_API_KEY,
            messages=[
                {"role": "system", "content": "You are a helpful analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

    try:
        response = await call_llm_api()
        return response.choices[0].message.content
    except Exception as e:
        log.error(f"Generation failed: {e}")
        return "Error generating response."
    