import fastapi_mail

from app.config import Config

email_config = fastapi_mail.ConnectionConfig(
    MAIL_USERNAME=Config.MAIL_USERNAME,
    MAIL_PASSWORD=Config.MAIL_PASSWORD,
    MAIL_FROM=Config.MAIL_FROM,
    MAIL_PORT=Config.MAIL_PORT,
    MAIL_SERVER=Config.MAIL_SERVER,
    MAIL_FROM_NAME=Config.MAIL_FROM_NAME,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=Config.MAIL_USE_TLS,
    VALIDATE_CERTS=Config.MAIL_USE_TLS,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER='./templates/',
)

fast_mail = fastapi_mail.FastMail(email_config)
