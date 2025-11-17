# app/models.py
# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base
import datetime
from pgvector.sqlalchemy import Vector

# นี่คือ "พิมพ์เขียว" ของตาราง "users"
class User(Base):
    __tablename__ = "users" # ชื่อตาราง

    # คอลัมน์ต่างๆ
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # (เราจะเพิ่ม Full Name, etc. ทีหลัง)

# (ต่อจาก class User)

# (ใหม่!) ตาราง "แม่" (เก็บแค่ "ชื่อไฟล์")
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User")
    # "บอก" ว่า Document 1 อัน... มี "Chunks" (ลูก) ได้หลายอัน
    chunks = relationship("Chunk", back_populates="document") 


# (ใหม่!) ตาราง "ลูก" (เก็บ "ชิ้นส่วน" + "Vector")
class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)

    # "เนื้อหา" ของ "ชิ้นส่วน" นี้
    text = Column(Text, nullable=False)

    # "Vector" (สมอง) ของ "ชิ้นส่วน" นี้
    # (384 คือ "มิติ" (Dimensions) ของ Model ที่เราจะใช้)
    embedding = Column(Vector(384)) 

    # "กุญแจ" ที่ชี้กลับไปหา "แม่"
    document_id = Column(Integer, ForeignKey("documents.id"))

    # "ความสัมพันธ์" (Magic)
    document = relationship("Document", back_populates="chunks")