import datetime as dt
import secrets

from jose import jwt
from passlib.context import CryptContext
from pydantic import SecretStr
from pydantic.dataclasses import dataclass

from app.config import Config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: str,
    expires_delta: dt.timedelta = None
) -> str:
    if expires_delta:
        expire = dt.datetime.utcnow() + expires_delta
    else:
        expire = dt.datetime.utcnow() + dt.timedelta(
            minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, Config.SECRET_KEY, algorithm=Config.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str | SecretStr, hashed_password: str) -> bool:
    return pwd_context.verify(
        plain_password.get_secret_value() if isinstance(plain_password, SecretStr) else plain_password,
        hashed_password,
    )


def get_password_hash(password: str | SecretStr) -> str:
    return pwd_context.hash(password.get_secret_value() if isinstance(password, SecretStr) else password)


@dataclass
class ResetCode:
    code: str
    hash: str


def generate_reset_code(nbytes=24) -> ResetCode:
    code = secrets.token_urlsafe(nbytes)
    hash = pwd_context.hash(code)
    return ResetCode(code=code, hash=hash)
