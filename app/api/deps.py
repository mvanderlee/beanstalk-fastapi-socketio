from typing import Annotated, AsyncGenerator, Generator, TypeAlias

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Config
from app.db import AIOSessionLocal, SessionLocal
from app.models.user import User
from app.schemas.auth import TokenData


# region - DB dependencies
def get_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


async def get_aio_db() -> AsyncGenerator[AsyncSession, None]:
    async with AIOSessionLocal() as session:
        yield session


RequestSession = Annotated[Session, Depends(get_db)]
RequestAsyncSession = Annotated[AsyncSession, Depends(get_aio_db)]
# endregion


# region - Auth dependencies
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_aio_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
        token_data = TokenData(**payload)
    except JWTError:
        raise credentials_exception

    user = await User.aio_get_by_email(email=token_data.sub, session=db)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

RequestUser = Annotated[User, Depends(get_current_active_user)]
# endregion
