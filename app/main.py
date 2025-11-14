# app/main.py
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Annotated

from app.config import settings
# --- Import "อาวุธ" ใหม่ของเรา ---
from app.security import (
    verify_password, 
    create_access_token, 
    verify_token,
    oauth2_scheme,  # <-- Import รปภ. มาจาก security
    TokenData,
    get_password_hash
)

# --- FAKE DATABASE (ยังคง Fake อยู่) ---
# นี่คือ Hash ของคำว่า "password" (สร้างจาก argon2)
hashed_password_for_intern = get_password_hash("password")

fake_users_db = {
    "intern": {
        "username": "intern",
        "full_name": "Intern Developer",
        "email": "intern@investigraph.com",
        "hashed_password": hashed_password_for_intern,
        "disabled": False,
    }
}

# --- Pydantic Models (เหมือนเดิม) ---
class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

# --- FastAPI App (เหมือนเดิม) ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0"
)

# --- Auth Functions (อัปเกรดแล้ว!) ---

def get_user(db, username: str):
    """(ย้ายมาจาก Fake Function เดิม) หา user ใน db"""
    if username in db:
        return db[username]
    return None

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    """
    นี่คือ "รปภ." ตัวจริง
    1. ตรวจ Token
    2. หา User ใน DB
    3. คืนค่า User object
    """
    # 1. ตรวจ Token (โดยใช้ verify_token จาก security.py)
    token_data: TokenData = await verify_token(token)
    
    # 2. หา User ใน DB (จาก username ที่อยู่ใน Token)
    user_data = get_user(fake_users_db, token_data.username)
    
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found (from token)",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. คืนค่า User object (ที่สะอาด ไม่มีรหัสผ่าน)
    return User(**user_data)


# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# Endpoint "Login" (อัปเกรดแล้ว!)
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    # 1. ตรวจสอบ User/Password (ของจริง!)
    user_data = get_user(fake_users_db, form_data.username)
    
    # 2. เช็กว่า user มีจริงไหม และ รหัสผ่านตรงกันไหม (ใช้ verify_password)
    if not user_data or not verify_password(
        form_data.password, user_data["hashed_password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. สร้าง Token (ของจริง!)
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    
    # "ไส้" (payload) ที่เราจะใส่ใน Token (เราจะใส่ username)
    token_data = {"sub": user_data["username"]} 
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# Endpoint ที่ "ถูกป้องกัน" (เหมือนเดิมเป๊ะๆ!)
@app.get("/users/me", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)]
):
    # ฟังก์ชันนี้ไม่ต้องแก้เลย
    # เพราะ "เวทมนตร์" ของ Depends(get_current_user)
    # มันจะไปเรียก "รปภ." (get_current_user) ที่อัปเกรดแล้วให้เราเอง!
    return current_user