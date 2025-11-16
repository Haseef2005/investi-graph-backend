import asyncio
import logging 
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, models, schemas # <-- Import ห้องครัว, ตาราง, API
from app.database import engine, Base, get_db # <-- Import เครื่องยนต์, รุ่นพ่อ, คนงาน
from app.config import settings
from app.security import (
    verify_password, 
    create_access_token, 
    verify_token,
    oauth2_scheme,
)
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, BackgroundTasks
import time
from app import processing
import sqlalchemy as sa

# --- "สร้าง" ตาราง (Table) ---
# เราจะบอกให้แอป "สร้างตาราง" (ถ้ายังไม่มี) ตอนที่มันเริ่มทำงาน
# (นี่คือวิธีง่ายๆ... Task ต่อไปเราจะใช้ "Alembic" ที่โปรขึ้น)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0"
)

# alembic จะจัดการเรื่องตารางให้เราเอง
# @app.on_event("startup")
# async def on_startup():
#     """Create the database tables on startup."""
#     async with engine.begin() as conn:
#         # await conn.run_sync(Base.metadata.drop_all) # <-- (ไว้ล้างตาราง ถ้าอยากเริ่มใหม่)
#         await conn.run_sync(Base.metadata.create_all)


# --- Auth Functions (อัปเกรดแล้ว!) ---

# เราจะ "เปลี่ยน" get_current_user ให้ "คุย" กับ DB จริง
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

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# (ใหม่!) Endpoint "สมัครสมาชิก" (Sign Up)
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


# Endpoint "Login" (อัปเกรดแล้ว!)
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db) # <-- "ฉีด" DB Session
):
    # 1. ตรวจสอบ User/Password (ใน DB จริง!)
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

    # 3. สร้าง Token (เหมือนเดิม)
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token_data = {"sub": user.username} 
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# Endpoint ที่ "ถูกป้องกัน" (อัปเกรดแล้ว!)
@app.get("/users/me", response_model=schemas.User)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    # ฟังก์ชันนี้ "แทบ" ไม่ต้องแก้เลย
    # มันจะคืนค่า User (จาก DB) ที่ "สะอาด" (ตาม response_model)
    # Pydantic (schemas.User) จะ "อ่าน" (from_attributes=True)
    # จาก current_user (models.User) ให้เราเอง
    return current_user

# Endpoint "รับข้อมูล"
@app.post("/documents/", response_model=schemas.Document)
async def create_document_and_upload_file(
    db: AsyncSession = Depends(get_db), 
    current_user: models.User = Depends(get_current_user), 
    file: UploadFile = File(...)
):
    # --- "แก้" ตรงนี้ (1/3) ---
    # "อ่าน" เนื้อใน (Bytes) "ทันที"
    content = await file.read()
    # ---------------------------

    db_doc = await crud.create_document(
        db=db, 
        filename=file.filename, 
        owner_id=current_user.id
    )

    # --- "แก้" ตรงนี้ (2/3) ---
    # "ส่ง" 'เนื้อใน' (content) เข้าไป... ไม่ใช่ 'ไฟล์' (object)
    asyncio.create_task(
        process_and_update_db(
            db=db, 
            doc_id=db_doc.id,
            filename=file.filename,
            content_type=file.content_type,
            content=content # <-- ส่ง "เนื้อใน"
        )
    )
    # ---------------------------

    return db_doc


# "ฟังก์ชัน" ที่จะรันเบื้องหลัง
async def process_and_update_db(
    db: AsyncSession, 
    doc_id: int,
    filename: str,      # <-- "แก้" (3/3) รับตัวแปรใหม่
    content_type: str,  # <-- "แก้" (3/3) รับตัวแปรใหม่
    content: bytes      # <-- "แก้" (3/3) รับตัวแปรใหม่
):
    """
    Task เบื้องหลัง (ที่เรียก "ห้องครัว" processing)
    """
    extracted_text = await processing.save_and_extract_text(
        # "ส่ง" ทุกอย่างต่อให้ "ห้องครัว"
        document_id=doc_id,
        filename=filename,
        content_type=content_type,
        content=content
    )

    if extracted_text is not None:
        await crud.update_document_text(
            db=db,
            document_id=doc_id,
            text=extracted_text
        )
    return

# (ใหม่!) Endpoint "ดูเอกสารทั้งหมด"
@app.get("/documents/", response_model=list[schemas.Document])
async def read_documents(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # (เราจะ "ขี้เกียจ" ... เราจะไปเขียน CRUD ทีหลัง)
    # (ตอนนี้... เราจะ "Query" มันตรงนี้เลย)
    stmt = (
        sa.select(models.Document)
        .where(models.Document.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all() # <-- คืนค่าทั้งหมด


# (ใหม่!) Endpoint "ดูเอกสาร (ฉบับเต็ม)"
@app.get("/documents/{doc_id}", response_model=schemas.DocumentDetail)
async def read_document_detail(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # (Query)
    stmt = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id) # <-- เช็กเจ้าของ
    )
    result = await db.execute(stmt)
    db_doc = result.scalar_one_or_none() # <-- หา 1 อัน

    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return db_doc