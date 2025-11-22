from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, schemas
from app.database import get_db
from app.dependencies import get_current_user
from app.controllers import user_controller

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.post("/", response_model=schemas.User)
async def create_user_endpoint(
    user: schemas.UserCreate,
    db: AsyncSession = Depends(get_db)
):
    return await user_controller.create_user(user, db)

@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    return current_user
