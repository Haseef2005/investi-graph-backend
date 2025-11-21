import asyncio
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, models, schemas
from app.database import get_db 
from app.config import settings
from app.security import (
    verify_password, 
    create_access_token, 
    verify_token,
    oauth2_scheme,
)
from app import processing
from app import sec_service
import sqlalchemy as sa
import os
from app.processing import UPLOAD_DIRECTORY
from app.knowledge_graph import check_neo4j_connection, close_neo4j_driver, get_document_graph, delete_document_graph
from contextlib import asynccontextmanager

# จัดการ Life Cycle (เปิด/ปิด Neo4j) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ตอนเริ่มแอป: เช็กการเชื่อมต่อ Neo4j
    if not await check_neo4j_connection():
        print("⚠️ WARNING: Could not connect to Neo4j!")
    
    yield # ปล่อยให้แอปทำงาน
    
    # ตอนปิดแอป: ปิดการเชื่อมต่อ
    await close_neo4j_driver()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan 
)

# --- Auth Functions ---

# get_current_user from db
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db) # <-- "ฉีด" DB Session เข้ามา
) -> models.User: # <-- คืนค่าเป็น "โมเดล" (DB)

    # 1. ตรวจ Token
    token_data: schemas.TokenData = await verify_token(token)

    # 2. หา User ใน DB จริง (โดยใช้ crud)
    user = await crud.get_user_by_username(db, username=token_data.username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found (from token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )

    return user

# --- Endpoints ---

# Root Endpoint
@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# Endpoint "สมัครสมาชิก" (Sign Up)
@app.post("/users/", response_model=schemas.User)
async def create_user_endpoint(
    user: schemas.UserCreate, # <-- รับ "พิมพ์เขียว" สมัคร
    db: AsyncSession = Depends(get_db)
):
    # 1. เช็กว่า email หรือ username ซ้ำไหม
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # 2. สร้าง User (โดย crud.py)
    return await crud.create_user(db=db, user=user)


# Endpoint "Login"
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db) # <-- "ฉีด" DB Session
):
    # 1. ตรวจสอบ User/Password จาก DB
    user = await crud.get_user_by_username(db, username=form_data.username)

    # 2. เช็กว่า user มีจริงไหม และ รหัสผ่านตรงกันไหม
    if not user or not verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )

    # 3. สร้าง Token 
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token_data = {"sub": user.username} 
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# Endpoint ที่ "ถูกป้องกัน" (ต้อง Login ก่อน)
@app.get("/users/me", response_model=schemas.User)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    return current_user

# Endpoint "อัปโหลดเอกสาร"
@app.post("/documents/", response_model=schemas.Document)
async def create_document_and_upload_file(
    db: AsyncSession = Depends(get_db), 
    current_user: models.User = Depends(get_current_user), 
    file: UploadFile = File(...)
):
    # (1) "อ่าน" เนื้อใน (เหมือนเดิม)
    content = await file.read()

    # (2) "สร้าง" ระเบียน "แม่" (Document)
    db_doc = await crud.create_document(
        db=db, 
        filename=file.filename, 
        owner_id=current_user.id
    )

    # (3) "โยน" งาน "หนัก" (extract, chunk, embed, save)
    asyncio.create_task(
        # (เรียก processing)
        processing.save_extract_chunk_and_embed( 
            document_id=db_doc.id,
            filename=file.filename,
            content_type=file.content_type,
            content=content
        )
    )

    # (4) "ตอบ" User กลับไป "ทันที"
    return db_doc

# Endpoint ดูรายการเอกสารของตัวเอง
@app.get("/documents/", response_model=list[schemas.Document])
async def read_documents(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # (Query)
    stmt = (
        sa.select(models.Document)
        .where(models.Document.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

# Endpoint "ดู Chunks ของเอกสาร"
@app.get("/documents/{doc_id}/chunks", response_model=list[schemas.Chunk])
async def read_document_chunks(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # (เราจะ "Query" 2 ชั้น... เพื่อ "ความปลอดภัย")

    # 1. "เช็ก" ว่า Document เป็นของเราไหม
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. "ดึง" "ลูก" (Chunks) ทั้งหมด
    stmt_chunks = (
        sa.select(models.Chunk)
        .where(models.Chunk.document_id == doc_id)
    )
    result_chunks = await db.execute(stmt_chunks)
    return result_chunks.scalars().all()

# Endpoint ถาม-ตอบ (RAG)
@app.post(
    "/documents/{doc_id}/query", 
    response_model=schemas.QueryResponse
)
async def query_document(
    doc_id: int,
    request: schemas.QueryRequest, # รับ JSON { "question": "..." }
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. ตรวจสอบสิทธิ์ (เป็นเจ้าของไฟล์ไหม?)
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. ค้นหา Chunks ที่เกี่ยวข้อง (Retrieve)
    relevant_chunks = await processing.retrieve_relevant_chunks(
        document_id=doc_id,
        query_text=request.question
    )

    # 3. ให้ AI ตอบคำถาม (Generate)
    answer = await processing.generate_answer(
        query=request.question,
        context_chunks=relevant_chunks,
        doc_id=doc_id
    )

    # 4. ส่งคำตอบกลับ
    return schemas.QueryResponse(
        answer=answer,
        context=relevant_chunks
    )

# Endpoint ถาม-ตอบ (Global Context) ---
@app.post(
    "/documents/query", # <--- ไม่มี {doc_id} แล้ว
    response_model=schemas.QueryResponse
)
async def query_all_documents(
    request: schemas.QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. ค้นหา Chunks จาก "ทุกไฟล์" ของ User
    relevant_chunks = await processing.retrieve_relevant_chunks_global(
        user_id=current_user.id,
        query_text=request.question
    )
    
    # 2. สร้างคำตอบ (ใช้ฟังก์ชันเดิม)
    answer = await processing.generate_answer(
        query=request.question,
        context_chunks=relevant_chunks,
        doc_id=None
    )
    
    return schemas.QueryResponse(
        answer=answer,
        context=relevant_chunks
    )

# Endpoint ลบเอกสาร ---
@app.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. เช็กว่ามีไฟล์จริงและเป็นของ User คนนี้ (เหมือนเดิม)
    stmt = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    db_doc = result.scalar_one_or_none()
    
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 2. ลบไฟล์ออกจาก Disk (เหมือนเดิม)
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{doc_id}_{db_doc.filename}")
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # 3. ลบกราฟออกจาก Neo4j ---
    # (สั่งลบก่อนลบใน DB เผื่อมี Error จะได้รู้ แต่จริงๆ ไว้หลังก็ได้)
    try:
        await delete_document_graph(doc_id)
    except Exception as e:
        print(f"⚠️ Failed to delete graph: {e}")
    # ------------------------------------

    # 4. ลบออกจาก Database (Cascade Rule จะลบ Chunks ใน PG ให้เอง)
    await crud.delete_document(db, doc_id)
    
    return None

# Endpoint ดึงกราฟ
@app.get("/documents/{doc_id}/graph", response_model=schemas.GraphData)
async def get_document_graph_data(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. เช็กสิทธิ์ก่อน (ห้ามคนอื่นแอบดูกราฟเรา)
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. ดึงข้อมูลจาก Neo4j
    graph_data = await get_document_graph(doc_id)
    
    return graph_data

# Endpoint ดึงงบจาก SEC
@app.post("/documents/fetch-sec")
async def fetch_sec_document(
    req: schemas.SecRequest,
    current_user: models.User = Depends(get_current_user)
):
    """
    Trigger background job to fetch 10-K from SEC EDGAR using asyncio
    """
    asyncio.create_task(
        sec_service.fetch_and_process_10k(
            user_id=current_user.id,
            ticker=req.ticker
        )
    )
    
    return {"message": f"Started fetching 10-K for {req.ticker}. Check your documents list in a few minutes."}
