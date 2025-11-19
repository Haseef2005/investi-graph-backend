import logging
import os
import aiofiles
from pypdf import PdfReader

# "Import" ตัว "หั่น" (Chunking) และ "แปลง" (Embedding)
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import models, crud
from app.database import SessionLocal
from app.config import settings
import sqlalchemy as sa
from litellm import acompletion

# Import Retry
from tenacity import retry, stop_after_attempt, wait_exponential

# --- (ใหม่!) Import Knowledge Graph Module ---
from app import knowledge_graph
# -------------------------------------------

UPLOAD_DIRECTORY = "/app/uploads"
log = logging.getLogger("uvicorn.error")

# --- "โหลด" AI (แค่ครั้งเดียว) ---
log.info("Loading SentenceTransformer model...")
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
log.info("Model loaded.")
# ---------------------------------


# "สร้าง" ตัว "หั่น"
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
    """
    Process: Upload -> Extract -> Chunk -> Embed (Vector) -> Extract (Graph) -> Save
    """
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{document_id}_{filename}")

    log.info(f"--- 🤖 TASK START (Doc ID: {document_id}) ---")

    try:
        # 1. Save File
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)
        log.info(f"File saved.")

        # 2. Extract Text
        extracted_text = ""
        if content_type == "application/pdf":
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
        else:
            extracted_text = content.decode("utf-8")
        log.info(f"Text extracted. Length: {len(extracted_text)}")

        # 3. Chunk
        chunks = text_splitter.split_text(extracted_text)
        log.info(f"Text chunked into {len(chunks)} pieces.")

        # --- 4.1 (RAG Pipeline) Embed & Save Vectors ---
        log.info(f"Embedding chunks (RAG)...")
        embeddings = EMBEDDING_MODEL.encode(chunks)
        
        db_chunks = []
        for i in range(len(chunks)):
            db_chunks.append(
                models.Chunk(
                    text=chunks[i],
                    embedding=embeddings[i],
                    document_id=document_id
                )
            )

        async with SessionLocal() as db:
            db.add_all(db_chunks)
            await db.commit()
        log.info(f"Vector embeddings saved to Postgres.")


        # --- 4.2 (KG Pipeline) Extract & Save Graph ---
        log.info(f"Extracting Knowledge Graph (Neo4j)...")
        
        # (Limit: ทำแค่ 5 ชิ้นแรกพอนะครับ เดี๋ยว Groq Rate Limit เต็ม)
        MAX_GRAPH_CHUNKS = 5 
        
        for i, chunk in enumerate(chunks):
            if i >= MAX_GRAPH_CHUNKS:
                log.info(f"Limit reached ({MAX_GRAPH_CHUNKS} chunks). Skipping remaining graph extraction.")
                break

            log.info(f"Processing Graph Chunk {i+1}/{min(len(chunks), MAX_GRAPH_CHUNKS)}...")
            
            # 1. ให้ AI แกะ Nodes/Edges
            graph_data = await knowledge_graph.extract_graph_from_text(chunk)
            
            # 2. บันทึกลง Neo4j
            await knowledge_graph.store_graph_data(document_id, graph_data)
            
        log.info(f"Knowledge Graph saved to Neo4j.")


        log.info(f"--- 🤖 TASK DONE (Doc ID: {document_id}) ---")

    except Exception as e:
        log.error(f"Error processing file {file_path}: {e}", exc_info=True)
        log.error(f"--- 🤖 TASK FAILED (Doc ID: {document_id}) ---")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        log.info(f"Cleaned up {file_path}")


# 1. ฟังก์ชัน "ค้นหา" (Retrieval) - Global
async def retrieve_relevant_chunks_global(
    user_id: int, 
    query_text: str
) -> list[models.Chunk]:
    log.info(f"Embedding global query: {query_text}")
    query_embedding = EMBEDDING_MODEL.encode(query_text)
    
    async with SessionLocal() as db:
        stmt = (
            sa.select(models.Chunk)
            .join(models.Document)
            .where(models.Document.owner_id == user_id)
            .order_by(
                models.Chunk.embedding.l2_distance(query_embedding)
            )
            .limit(5)
        )
        result = await db.execute(stmt)
        return result.scalars().all()


async def retrieve_relevant_chunks(
    document_id: int, 
    query_text: str
) -> list[models.Chunk]:
    log.info(f"Embedding query: {query_text}")
    query_embedding = EMBEDDING_MODEL.encode(query_text)

    async with SessionLocal() as db:
        stmt = (
            sa.select(models.Chunk)
            .where(models.Chunk.document_id == document_id)
            .order_by(
                models.Chunk.embedding.l2_distance(query_embedding)
            )
            .limit(5)
        )
        result = await db.execute(stmt)
        return result.scalars().all()


# 2. ฟังก์ชัน "สร้างคำตอบ" (Generation)
async def generate_answer(
    query: str, 
    context_chunks: list[models.Chunk]
) -> str:
    log.info(f"Generating answer using {len(context_chunks)} chunks...")

    context_text = "\n\n---\n\n".join(
        [chunk.text for chunk in context_chunks]
    )

    prompt = f"""
    You are an expert financial analyst AI.
    Answer the user's question based *only* on the context provided below.
    If the answer is not found in the context, say "I cannot find the answer in the provided context."

    CONTEXT:
    ---
    {context_text}
    ---

    QUESTION:
    {query}
    """

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
        answer = response.choices[0].message.content
        log.info(f"Answer generated.")
        return answer

    except Exception as e:
        log.error(f"LLM completion failed after retries: {e}", exc_info=True)
        return f"Error: The AI service is currently unavailable. Please try again later. ({str(e)})"