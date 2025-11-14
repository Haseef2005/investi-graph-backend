# app/schemas.py
from pydantic import BaseModel, EmailStr

# --- Pydantic Models (Schemas) ---

# 1. Schema "พื้นฐาน" (Base)
#    ฟิลด์ที่ใช้ร่วมกัน
class UserBase(BaseModel):
    username: str
    email: EmailStr

# 2. Schema สำหรับ "สร้าง" (Create)
#    (ใช้รับข้อมูลตอน POST /users/)
#    สืบทอดจาก Base และเพิ่ม "password"
class UserCreate(UserBase):
    password: str # <-- รับ password ธรรมดา

# 3. Schema สำหรับ "อ่าน" (Read)
#    (ใช้เป็น response_model)
#    สืบทอดจาก Base และเพิ่ม "id"
#    (ไม่มี password หลุดออกไป!)
class User(UserBase):
    id: int
    is_active: bool

    # บอก Pydantic ให้อ่านจาก "โมเดล" (ORM) ได้
    # (จากเดิมที่มันอ่านจาก Dict)
    class Config:
        from_attributes = True # <-- (ชื่อเก่าคือ orm_mode)

# (Schema ของ Token ไม่ต้องย้ายมาก็ได้ แต่ย้ายมาก็ดี)
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None