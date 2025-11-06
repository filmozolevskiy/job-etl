from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Sequence

from .base import NotificationChannel, NotificationMessage


class EmailChannel(NotificationChannel):
    """
    SMTP-backed email channel.

    Configuration via environment variables:
      - SMTP_HOST (required)
      - SMTP_PORT (optional, default 587)
      - SMTP_USER (optional)
      - SMTP_PASSWORD (optional; read from /run/secrets/smtp_password if not set)
      - SMTP_FROM (required)
      - NOTIFY_TO (comma-separated list of recipients; required)
      - SMTP_USE_TLS (optional, default 'true')
      - SMTP_USE_SSL (optional, default 'false')
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        sender: Optional[str] = None,
        recipients: Optional[Sequence[str]] = None,
        use_tls: Optional[bool] = None,
        use_ssl: Optional[bool] = None,
    ) -> None:
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER")
        self.smtp_password = smtp_password or self._resolve_password()
        self.sender = sender or os.getenv("SMTP_FROM")
        self.recipients = list(recipients) if recipients is not None else self._resolve_recipients()
        self.use_tls = use_tls if use_tls is not None else os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.use_ssl = use_ssl if use_ssl is not None else os.getenv("SMTP_USE_SSL", "false").lower() == "true"

        if not self.smtp_host:
            raise ValueError("SMTP_HOST must be configured")
        if not self.sender:
            raise ValueError("SMTP_FROM must be configured")
        if not self.recipients:
            raise ValueError("NOTIFY_TO must be configured with at least one recipient")

    def _resolve_password(self) -> Optional[str]:
        password = os.getenv("SMTP_PASSWORD")
        if password:
            return password
        secret_path = "/run/secrets/smtp_password"
        if os.path.exists(secret_path):
            try:
                with open(secret_path, encoding="utf-8") as f:
                    return f.read().strip()
            except UnicodeDecodeError:
                with open(secret_path, encoding="utf-16") as f:
                    return f.read().strip()
        return None

    def _resolve_recipients(self) -> Sequence[str]:
        raw = os.getenv("NOTIFY_TO", "")
        return [r.strip() for r in raw.split(",") if r.strip()]

    def send(self, message: NotificationMessage) -> None:
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = self.sender
        email["To"] = ", ".join(self.recipients)
        if message.html:
            email.set_content(message.text)
            email.add_alternative(message.html, subtype="html")
        else:
            email.set_content(message.text)

        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                self._maybe_login(server)
                server.send_message(email)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                self._maybe_login(server)
                server.send_message(email)

    def _maybe_login(self, server: smtplib.SMTP) -> None:
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)


