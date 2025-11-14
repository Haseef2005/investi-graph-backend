# app/models.py
from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base # <-- Import "รุ่นพ่อ"

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