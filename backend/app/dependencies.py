from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud, models, schemas
from app.security import verify_token, oauth2_scheme

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> models.User:
    """
    Dependency to get the current authenticated user.
    """
    # 1. Verify Token
    token_data: schemas.TokenData = await verify_token(token)

    # 2. Find User in DB
    user = await crud.get_user_by_username(db, username=token_data.username)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found (from token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )

    return user
