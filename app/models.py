# app/models.py
# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

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

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True, nullable=False)

    # (เราจะ "เก็บ" text ที่สกัดได้ไว้ที่นี่)
    extracted_text = Column(Text, nullable=True) 

    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    # "กุญแจ" ที่ชี้กลับไปหา "เจ้าของ"
    owner_id = Column(Integer, ForeignKey("users.id"))

    # "ความสัมพันธ์" (Magic)
    # บอก SQLAlchemy ว่า "owner" คือ User นะ
    owner = relationship("User")