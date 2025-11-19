from pydantic import BaseModel, EmailStr
from pydantic import BaseModel, EmailStr, Field
import datetime

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

class DocumentBase(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime.datetime # <-- Import datetime ด้วย

class Document(DocumentBase):
    owner_id: int

    class Config:
        from_attributes = True

# --- Document Schemas (ใหม่) ---

class Document(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime.datetime
    owner_id: int

    class Config:
        from_attributes = True

# (ใหม่!)
class Chunk(BaseModel):
    id: int
    text: str
    document_id: int

    class Config:
        from_attributes = True

# (ใหม่!) รับคำถาม
class QueryRequest(BaseModel):
    question: str

# (ใหม่!) ส่งคำตอบ + บริบท
class QueryResponse(BaseModel):
    answer: str
    context: list[Chunk] # Reuse schema 'Chunk' ที่มีอยู่แล้ว

# --- Graph Schemas (สำหรับ Task 10) ---
class GraphNode(BaseModel):
    id: str
    label: str
    type: str

class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str

class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]