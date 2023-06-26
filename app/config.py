import os
from typing import Any

truthy_strings = ('Y', 'YES', 'T', 'TRUE', '1', 'ON')


def get_or_raise(key: str, message: str = None) -> Any:
    value = os.getenv(key)
    if value is None:
        if message is None:
            message = f"Config variable '{key}' is required but not provided!"

        raise ValueError(message)

    return value


def get_bool(key: str, default: bool = True) -> bool:
    return (os.environ.get(key, str(default)).upper() in truthy_strings)


class Config:

    APP_BASE_URL = os.getenv('APP_BASE_URL', "http://localhost:8000/")

    # to get a new secret key:
    # openssl rand -hex 32
    SECRET_KEY = get_or_raise('SECRET_KEY')
    ALGORITHM = os.getenv('ALGORITHM', "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 300)
    RESET_TOKEN_EXPIRE_MINUTES = os.getenv('RESET_TOKEN_EXPIRE_MINUTES', 60)

    # Mail Config
    MAIL_SERVER = get_or_raise('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 1025))
    MAIL_USERNAME = get_or_raise('MAIL_USERNAME')
    MAIL_PASSWORD = get_or_raise('MAIL_PASSWORD')
    MAIL_USE_TLS = get_bool('MAIL_USE_TLS')

    MAIL_FROM = os.getenv('MAIL_FROM', "cuwep@cuwep.com")
    MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', "CUWEP")
