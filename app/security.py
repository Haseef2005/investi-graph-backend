# app/security.py
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError
from app.config import settings 

# --- Password Hashing ---

# 1. เราสร้าง "พิมพ์" สำหรับการ hash
#    เราบอกว่า "เราจะใช้ 'argon2' เป็นหลักนะ"
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 2. ฟังก์ชันสำหรับ "เทียบ" รหัสผ่าน
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """เทียบรหัสผ่านจริง กับ รหัสผ่านที่ hash ไว้"""
    return pwd_context.verify(plain_password, hashed_password)

# 3. ฟังก์ชันสำหรับ "สร้าง" hash (เผื่อไว้ใช้ตอนสมัครสมาชิก)
def get_password_hash(password: str) -> str:
    """สร้าง hash จากรหัสผ่าน"""
    return pwd_context.hash(password)


# --- JWT (Token) Handling ---

# นี่คือ "รปภ." ที่คอยดึง Token จาก Header
# เราย้ายมาที่นี่ เพื่อให้ get_current_user เรียกใช้ได้
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic model สำหรับ "ข้อมูล" ที่จะยัดไส้ใน JWT
class TokenData(BaseModel):
    username: str | None = None

# 4. ฟังก์ชันสำหรับ "สร้าง" JWT Token
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """สร้าง JWT Access Token"""
    to_encode = data.copy()
    
    # กำหนดวันหมดอายุ
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # ถ้าไม่กำหนด ก็ให้หมดอายุใน 15 นาที
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    
    # "เข้ารหัส" (Encode) ข้อมูล + ลายเซ็น
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

# 5. ฟังก์ชันสำหรับ "ตรวจสอบ" JWT Token (นี่คือหัวใจของ รปภ.)
async def verify_token(token: str) -> TokenData:
    """
    ตรวจสอบ (Decode & Verify) JWT Token
    ถ้าผ่าน: คืนข้อมูล (payload)
    ถ้าไม่ผ่าน: โยน HTTPException
    """
    
    # นี่คือ Error ที่เราจะโยน ถ้า Token ใช้ไม่ได้
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # "ถอดรหัส" (Decode) Token โดยใช้ Secret Key
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # ดึง username ออกจาก "ไส้" (payload)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # ตรวจสอบว่า "ไส้" มันตรงตาม "พิมพ์เขียว" (TokenData) ของเราไหม
        token_data = TokenData(username=username)
    
    except JWTError: # ถ้าลายเซ็นไม่ตรง หรือ หมดอายุ
        raise credentials_exception
    except ValidationError: # ถ้า "ไส้" (payload) หน้าตาไม่เหมือน TokenData
        raise credentials_exception
        
    return token_data