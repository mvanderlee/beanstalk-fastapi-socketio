import os
from typing import AsyncContextManager, Callable
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError('No database URL provided. Please set the DATABASE_URL environment variable')

url = urlparse(DATABASE_URL)

engine_args = {}

if url.scheme in ('postgresql', 'postgresql+asyncpg'):
    db_url = url._replace(scheme='postgresql').geturl()
    aio_db_url = url._replace(scheme='postgresql+asyncpg').geturl()

else:
    raise ValueError('Only postgresql are currently supported. Contact your system administrator to request additional databases.')


engine = create_engine(db_url, **engine_args)
SessionLocal: Callable[[], Session] = sessionmaker(autocommit=False, autoflush=False, bind=engine)

aio_engine = create_async_engine(aio_db_url, **engine_args)
AIOSessionLocal: Callable[[], AsyncContextManager[AsyncSession]] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=aio_engine,
    class_=AsyncSession,
)
