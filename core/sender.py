"""Sender SMTP para digest por email (SDD §6.2)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class SmtpSender:
    """Envía emails vía SMTP de Gmail (requiere App Password)."""

    GMAIL_SMTP = "smtp.gmail.com"
    GMAIL_PORT = 587

    def __init__(
        self,
        email: str | None = None,
        app_password: str | None = None,
    ):
        self.email = email or os.getenv("GMAIL_ADDRESS", "")
        self.app_password = app_password or os.getenv("GMAIL_APP_PASSWORD", "")

    def send(self, to: str, subject: str, html_body: str) -> bool:
        """Envía un email."""
        if not self.email or not self.app_password:
            logger.error("SMTP: missing email or app_password")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.email
            msg["To"] = to

            # Attatch HTML
            part = MIMEText(html_body, "html")
            msg.attach(part)

            # Connect y enviar
            with smtplib.SMTP(self.GMAIL_SMTP, self.GMAIL_PORT) as server:
                server.starttls()
                server.login(self.email, self.app_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to}")
            return True

        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            return False
