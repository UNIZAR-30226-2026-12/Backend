import os
import aiosmtplib
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


async def send_new_password_email(to_email: str, new_password: str):
    body = (
        "Hola,\n\n"
        "Hemos recibido una solicitud para recuperar el acceso a tu cuenta de Reversi.\n\n"
        "Tu nueva contraseña es:\n\n"
        f"    {new_password}\n\n"
        "Puedes iniciar sesión con ella en cualquier momento.\n"
        "Te recomendamos cambiarla por una propia en cuanto accedas.\n\n"
        "Si no solicitaste este cambio, contacta con nosotros respondiendo a este correo.\n\n"
        "— El equipo de Reversi\n"
    )

    message = MIMEText(body, "plain", "utf-8")
    message["From"] = SMTP_USER
    message["To"] = to_email
    message["Subject"] = "Tu nueva contraseña de Reversi"

    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        start_tls=True,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
    )
