from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, schemas

async def create_user(user: schemas.UserCreate, db: AsyncSession):
    # 1. Check if email or username already exists
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = await crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # 2. Create User
    return await crud.create_user(db=db, user=user)
