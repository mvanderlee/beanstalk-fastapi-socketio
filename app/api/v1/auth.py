import datetime as dt
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_mail import MessageSchema, MessageType
from loguru import logger
from pydantic import EmailStr

from app.api.deps import RequestAsyncSession
from app.api.exceptions import AuthenticationFailed, UnprocessableInput
from app.config import Config
from app.core.email import fast_mail
from app.core.security import (
    create_access_token,
    generate_reset_code,
    get_password_hash,
    pwd_context,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import PasswordResetDTO, RegisterUserDTO, Token, UserCodeDTO
from app.schemas.user import UserDTO
from app.utils import requote_uri

router = APIRouter(prefix='/v1/auth')


@router.post('/register')
async def register_user(
    user_data: RegisterUserDTO,
    background_tasks: BackgroundTasks,
    db: RequestAsyncSession,
) -> UserDTO:
    '''
        Register the user and send a confirmation email to the user.
    '''
    logger.info('POST Register User', email=user_data.email)

    code = generate_reset_code(nbytes=24)
    user = await User.aio_create(
        {
            'email': user_data.email,
            'password_hash': get_password_hash(user_data.password.get_secret_value()),
            'reset_code_hash': code.hash,
            'reset_code_expiration': dt.datetime.now() + dt.timedelta(minutes=Config.RESET_TOKEN_EXPIRE_MINUTES),
        },
        session=db,
    )

    # Prepare confirmation email, and schedule sending
    message = MessageSchema(
        subject="Registration confirmation",
        recipients=[user.email],
        template_body={
            "link": f"{Config.APP_BASE_URL}confirm?email={requote_uri(user.email)}&code={code.code}",
            "email": user.email,
        },
        subtype=MessageType.html
    )
    background_tasks.add_task(fast_mail.send_message, message, template_name='auth/confirm_email.html')

    return user


@router.post('/confirm')
async def confirm_user(
    confirm_data: UserCodeDTO,
    db: RequestAsyncSession,
):
    '''
        Confirm the user. The code was included in the confirmation email send to the user.
    '''
    logger.info('POST confirm user', email=confirm_data.email)

    user = await User.aio_get_by_email(confirm_data.email, session=db)
    if not user:
        logger.warning('Attempted confirming of unknown user', email=confirm_data.email)
        pwd_context.dummy_verify()  # Simulate time it would take to hash a password.
        raise AuthenticationFailed('Invalid or expired reset code')

    if not user.verify_reset_code(confirm_data.code):
        logger.warning('Attempted confirming of user with invalid code', email=confirm_data.email)
        raise AuthenticationFailed('Invalid or expired reset code')

    if user.is_active:
        logger.warning('User is already active')
        raise AuthenticationFailed('User is already activated')

    user = await user.aio_update(
        {
            'is_active': True,
            'confirmed_at': dt.datetime.now(),
            'reset_code_hash': None,
            'reset_code_expiration': None,
        },
        session=db
    )


@router.post("/login")
async def authenticate_user(
    login_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: RequestAsyncSession,
) -> Token:
    '''
        Log the user in and return a JWT token to use for all other requests
    '''
    logger.info("Login attempt for user {}".format(login_data.username))
    user = await User.aio_get_by_email(email=login_data.username, session=db)

    if not user:
        logger.warning('Login failed, user not found.', email=login_data.username)
        pwd_context.dummy_verify()  # Simulate time it would take to hash a password.
        raise AuthenticationFailed()

    if user.confirmed_at is None:
        logger.warning('Login failed, user is not activated.', email=login_data.username)
        pwd_context.dummy_verify()  # Simulate time it would take to hash a password.
        raise AuthenticationFailed()

    if not verify_password(login_data.password, user.password_hash):
        logger.warning('Login failed, user provided an incorrect password.', email=login_data.username)
        raise AuthenticationFailed()

    # Login credentials have been validated. Continue on.
    access_token = create_access_token(subject=login_data.username)

    return Token(access_token, "bearer")


@router.post('/forgot_password')
async def send_password_reset_email(
    email: Annotated[EmailStr, Body(embed=True)],
    background_tasks: BackgroundTasks,
    db: RequestAsyncSession,
):
    '''
        Initialize the forgotten password flow.
        This sends an email to the user with a link to actually reset the password
    '''
    logger.info('POST forgot password', email=email)

    code = generate_reset_code(nbytes=24)  # Generate here so it's included in the request time even if no user is found.

    user = await User.aio_get_by_email(email, session=db)
    if user is None:
        # Just return a 200. From a security perspective we do not want a potential attacker
        # to know if an email is registered with us
        return {}

    user = await user.aio_update(
        {
            'reset_code_hash': code.hash,
            'reset_code_expiration': dt.datetime.now() + dt.timedelta(minutes=Config.RESET_TOKEN_EXPIRE_MINUTES),
        },
        session=db
    )

    # Prepare confirmation email, and schedule sending
    message = MessageSchema(
        subject="Password reset email",
        recipients=[user.email],
        template_body={
            "link": f"{Config.APP_BASE_URL}reset_password?email={requote_uri(user.email)}&code={code.code}",
            "email": user.email,
        },
        subtype=MessageType.html
    )
    background_tasks.add_task(fast_mail.send_message, message, template_name='auth/reset_email.html')

    # Don't return anything, just a 200 - success
    return {}


@router.post("/check_reset_code")
async def check_password_reset_code(
    request_data: UserCodeDTO,
    db: RequestAsyncSession,
):
    '''
        Checks if the reset code is valid. This does not reset the codes.
        The usecase here is to allow the UI to be able to detect if the code is valid
        before having the user enter the new password.
    '''
    user = await User.aio_get_by_email(request_data.email, session=db)
    if not user:
        logger.warning('Attempted reset of unknown user', email=request_data.email)
        pwd_context.dummy_verify()  # Simulate time it would take to hash a password.
        raise AuthenticationFailed('Invalid or expired reset code')

    if not user.verify_reset_code(request_data.code):
        logger.warning('Attempted reset of user with invalid code', email=request_data.email)
        raise AuthenticationFailed('Invalid or expired reset code')

    # Don't return anything, just a 200 - success
    return {}


@router.post("/reset_password")
async def reset_password(
    request_data: PasswordResetDTO,
    db: RequestAsyncSession,
) -> Token:
    '''
        Actually reset the password with all included validations
    '''
    user = await User.aio_get_by_email(request_data.email, session=db)
    if not user:
        logger.warning('Attempted reset of unknown user', email=request_data.email)
        pwd_context.dummy_verify()  # Simulate time it would take to hash a password.
        raise AuthenticationFailed('Invalid or expired reset code')

    if not user.verify_reset_code(request_data.code):
        logger.warning('Attempted reset of user with invalid code', email=request_data.email)
        raise AuthenticationFailed('Invalid or expired reset code')

    if verify_password(request_data.password, user.password_hash):
        raise UnprocessableInput('New password may not be identical to the previous one')

    # Password is okay, update in database
    await user.aio_update(
        {
            'password_hash': get_password_hash(request_data.password),
            'reset_code_hash': None,
            'reset_code_expiration': None,
        },
        session=db,
    )

    # Login credentials have been validated. Continue on.
    access_token = create_access_token(subject=request_data.email)

    return Token(access_token, "bearer")
