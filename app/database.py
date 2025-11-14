# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# 1. สร้าง "เครื่องยนต์" (Engine)
#    นี่คือ "โรงงาน" ที่สร้างการเชื่อมต่อ
#    echo=True คือให้มัน "บ่น" (Log) SQL ที่มันรันออกมา (ดีสำหรับ Debug)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, 
)

# 2. สร้าง "พิมพ์เขียว" ของ Session
#    Session คือ "คนงาน" ที่เราจะจ้างไปคุยกับ DB
SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False, # <-- สำคัญสำหรับ async
)

# 3. สร้าง "Base Class"
#    นี่คือ "รุ่นพ่อ" ที่ Model (ตาราง) ของเราทั้งหมดจะสืบทอด
class Base(DeclarativeBase):
    pass

# ฟังก์ชันสำหรับ "ฉีด" (Inject) Session เข้าไปใน API
async def get_db():
    """Dependency to get a DB session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit() # <-- Commit ถ้าทุกอย่าง OK
        except Exception:
            await session.rollback() # <-- Rollback ถ้ามีอะไรพัง
            raise
        finally:
            await session.close()