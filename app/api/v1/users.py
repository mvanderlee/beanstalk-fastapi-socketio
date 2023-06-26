import datetime as dt

from fastapi import APIRouter, BackgroundTasks
from fastapi_mail import MessageSchema, MessageType
from loguru import logger

from app.api.deps import RequestAsyncSession, RequestUser
from app.config import Config
from app.core.email import fast_mail
from app.core.security import generate_reset_code
from app.models.user import User
from app.schemas import PageableResponseDTO
from app.schemas.user import UserDTO
from app.utils import requote_uri

router = APIRouter(prefix='/v1/users')


@router.get('')
async def get_users(
    db: RequestAsyncSession,
    current_user: RequestUser,
) -> PageableResponseDTO[UserDTO]:
    logger.info('GET Users', current_user=current_user.email)
    return await User.aio_get_all(session=db)


@router.post('/resend_confirmation')
async def resend_confirmation_email(
    email: str,
    background_tasks: BackgroundTasks,
    db: RequestAsyncSession,
    current_user: RequestUser,
):
    user = await User.aio_get_by_email(email, session=db, raise_if_not_found=True)

    code = generate_reset_code(nbytes=24)
    user = await user.aio_update(
        {
            'reset_code_hash': code.hash,
            'reset_code_expiration': dt.datetime.now() + dt.timedelta(minutes=Config.RESET_TOKEN_EXPIRE_MINUTES),
        },
        session=db
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
