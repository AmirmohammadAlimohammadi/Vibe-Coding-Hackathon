from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from functools import lru_cache


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


class OtpEmailSender:
    def __init__(self) -> None:
        self.mode = os.getenv("EMAIL_DELIVERY_MODE", "smtp").strip().lower()

    @staticmethod
    def _enabled(name: str, default: str) -> bool:
        return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

    def send(self, recipient: str, code: str, expires_in: int) -> None:
        if self.mode == "console":
            logger.warning("Development OTP for %s: %s", recipient, code)
            return
        if self.mode != "smtp":
            raise EmailDeliveryError("EMAIL_DELIVERY_MODE must be 'smtp' or 'console'")

        host = os.getenv("SMTP_HOST", "").strip()
        from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
        if not host or not from_email:
            raise EmailDeliveryError("SMTP_HOST and SMTP_FROM_EMAIL are required")

        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USERNAME", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
        use_ssl = self._enabled("SMTP_USE_SSL", "false")
        use_tls = self._enabled("SMTP_USE_TLS", "true")
        from_name = os.getenv("SMTP_FROM_NAME", "Liara Assistant").strip()

        message = EmailMessage()
        message["Subject"] = "Your Liara Assistant login code"
        message["From"] = f"{from_name} <{from_email}>"
        message["To"] = recipient
        message.set_content(
            f"Your login code is: {code}\n\n"
            f"This code expires in {expires_in // 60} minutes. "
            "If you did not request it, you can ignore this email."
        )

        try:
            context = ssl.create_default_context()
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
                    self._authenticate_and_send(smtp, username, password, message)
                return
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls(context=context)
                    smtp.ehlo()
                self._authenticate_and_send(smtp, username, password, message)
        except (OSError, smtplib.SMTPException) as error:
            raise EmailDeliveryError("Unable to send the login code") from error

    @staticmethod
    def _authenticate_and_send(
        smtp: smtplib.SMTP,
        username: str,
        password: str,
        message: EmailMessage,
    ) -> None:
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


@lru_cache(maxsize=1)
def get_email_sender() -> OtpEmailSender:
    return OtpEmailSender()
