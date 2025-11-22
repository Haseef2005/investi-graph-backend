import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import models, schemas
from app.security import get_password_hash

# --- CRUD Functions ---

# "R" - Read
async def get_user_by_username(db: AsyncSession, username: str):
    """
    ค้นหา User ด้วย username
    """
    result = await db.execute(
        select(models.User).filter(models.User.username == username)
    )
    return result.scalar_one_or_none()

async def get_user_by_email(db: AsyncSession, email: str):
    """
    ค้นหา User ด้วย email (กันสมัครซ้ำ)
    """
    result = await db.execute(
        select(models.User).filter(models.User.email == email)
    )
    return result.scalar_one_or_none()

# "C" - Create User
async def create_user(db: AsyncSession, user: schemas.UserCreate):
    """
    สร้าง User ใหม่
    """
    # 1. "ปั่น" รหัสผ่าน
    hashed_password = get_password_hash(user.password)

    # 2. สร้าง "โมเดล" (DB) จาก "สกีมา" (API)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
        # is_active จะเป็น True โดย default
    )

    # 3. "เพิ่ม" (Add) และ "คอมมิต" (Commit)
    db.add(db_user)
    await db.commit() # <-- Commit (เพราะ get_db จะไม่ commit ให้เรา)
    await db.refresh(db_user) # <-- Refresh (เพื่อให้ได้ id ที่เพิ่งสร้าง)

    return db_user

# "C" - Create Document
async def create_document(
    db: AsyncSession, 
    filename: str, 
    owner_id: int
) -> models.Document:
    """
    สร้าง Record ของ Document แบบ "ว่างเปล่า"
    """
    db_document = models.Document(
        filename=filename,
        owner_id=owner_id
    )
    db.add(db_document)
    await db.commit()
    await db.refresh(db_document) # <-- Refresh (เพื่อให้ได้ ID)
    return db_document

# "D" - Delete Document
async def delete_document(db: AsyncSession, document_id: int):
    # Cascade Delete จาก models.py
    stmt = sa.delete(models.Document).where(models.Document.id == document_id)
    await db.execute(stmt)
    await db.commit()
    return