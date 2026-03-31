import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


async def send_reset_email(to_email: str, reset_code: str):
    message = MIMEMultipart("alternative")
    message["From"] = SMTP_USER
    message["To"] = to_email
    message["Subject"] = "Reversi - Restablecer contraseña"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0F0F1A; color: #E0E0E0; padding: 40px;">
        <div style="max-width: 500px; margin: 0 auto; background-color: #1A1A2E; border-radius: 12px; padding: 32px; border: 1px solid #2A2A4A;">
            <h1 style="color: #6C63FF; text-align: center; margin-bottom: 24px;">Reversi</h1>
            <p style="font-size: 16px; text-align: center;">Has solicitado restablecer tu contraseña.</p>
            <p style="font-size: 16px; text-align: center;">Tu código de verificación es:</p>
            <div style="background-color: #25253E; border-radius: 8px; padding: 16px; text-align: center; margin: 24px 0;">
                <span style="font-size: 32px; font-weight: bold; color: #6C63FF; letter-spacing: 8px;">{reset_code}</span>
            </div>
            <p style="font-size: 14px; color: #8888AA; text-align: center;">Este código expira en 15 minutos.</p>
            <p style="font-size: 14px; color: #8888AA; text-align: center;">Si no solicitaste este cambio, ignora este correo.</p>
        </div>
    </body>
    </html>
    """

    message.attach(MIMEText(html_content, "html"))

    await aiosmtplib.send(
        message,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        start_tls=True,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
    )
