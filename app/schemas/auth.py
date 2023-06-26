import re

from pydantic import EmailStr, SecretStr, validator
from pydantic.dataclasses import dataclass


@dataclass
class RegisterUserDTO:
    email: EmailStr
    password: SecretStr

    @validator('password')
    def password_requirements(cls, value: SecretStr):
        '''
            Must be at least 8 character  - ".{8,}"
            Must contain at least one uppercase letter  - "(?=.*[A-Z])"
            Must contain at least one lowercase letter  - "(?=.*[a-z])"
            Must contain at least one digit  - "(?=.*\\d)"
            Must contain at least one special character  - "(?=.*[^a-zA-Z\\d\\s])"
        '''
        pattern = r"^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[^a-zA-Z\d\s]).{8,}$"
        if not re.match(pattern, value.get_secret_value()):
            raise ValueError('Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character.')

        return value


@dataclass
class PasswordResetDTO(RegisterUserDTO):
    code: str


@dataclass
class UserCodeDTO:
    email: EmailStr
    code: str


@dataclass
class Token:
    access_token: str
    token_type: str


@dataclass
class TokenData:
    sub: str | None = None
