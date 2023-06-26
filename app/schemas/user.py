import datetime as dt
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, EmailStr
from pydantic.dataclasses import dataclass


@dataclass(config=ConfigDict(orm_mode=True))
class UserDTO:
    '''Read user model'''
    id: UUID
    email: EmailStr

    is_active: bool
    confirmed_at: Optional[dt.datetime] = None

    last_login_at: Optional[dt.datetime] = None
    last_login_ip: Optional[str] = None
