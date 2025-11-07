from __future__ import annotations

import os
import smtplib
import ssl
from collections.abc import Sequence
from email.message import EmailMessage

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
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        sender: str | None = None,
        recipients: Sequence[str] | None = None,
        use_tls: bool | None = None,
        use_ssl: bool | None = None,
    ) -> None:
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST")
        # Validate and parse SMTP port
        port_str = os.getenv("SMTP_PORT", "587")
        try:
            self.smtp_port = smtp_port or int(port_str)
        except ValueError as err:
            raise ValueError(f"SMTP_PORT must be numeric, got: {port_str}") from err
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

    def _resolve_password(self) -> str | None:
        """
        Resolve SMTP password from environment variable or Docker secret file.

        Checks in order:
        1. SMTP_PASSWORD environment variable
        2. /run/secrets/smtp_password file (Docker secrets)

        Returns:
            str | None: SMTP password if found, None otherwise.

        Note:
            Attempts UTF-8 encoding first, falls back to UTF-16 if needed.
        """
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
        """
        Parse recipient email addresses from NOTIFY_TO environment variable.

        The NOTIFY_TO variable should contain comma-separated email addresses.
        Whitespace around addresses is automatically trimmed.

        Returns:
            Sequence[str]: List of recipient email addresses. Empty list if
                NOTIFY_TO is not set or contains no valid addresses.
        """
        raw = os.getenv("NOTIFY_TO", "")
        return [r.strip() for r in raw.split(",") if r.strip()]

    def send(self, message: NotificationMessage) -> None:
        """
        Send an email notification via SMTP.

        Constructs an EmailMessage with the notification content and sends it
        to all configured recipients. Supports both plain text and HTML content.
        Uses SSL or TLS encryption based on configuration.

        Args:
            message: The notification message to send.

        Raises:
            smtplib.SMTPException: If SMTP server communication fails.
            smtplib.SMTPAuthenticationError: If authentication fails.
            ValueError: If email addresses are invalid.

        Note:
            - If both text and HTML are provided, the email will be sent as
              multipart/alternative with text as primary and HTML as alternative.
            - Authentication is only attempted if SMTP_USER and SMTP_PASSWORD
              are configured.
        """
        # Build email message
        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = self.sender
        email["To"] = ", ".join(self.recipients)

        # Set content: if HTML provided, send multipart with text fallback
        if message.html:
            email.set_content(message.text)
            email.add_alternative(message.html, subtype="html")
        else:
            email.set_content(message.text)

        # Send via SMTP with appropriate security (SSL or TLS)
        if self.use_ssl:
            # Use SSL connection (port typically 465)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                self._maybe_login(server)
                server.send_message(email)
        else:
            # Use STARTTLS (port typically 587) or unencrypted
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                self._maybe_login(server)
                server.send_message(email)

    def _maybe_login(self, server: smtplib.SMTP) -> None:
        """
        Authenticate with SMTP server if credentials are configured.

        Only attempts login if both SMTP_USER and SMTP_PASSWORD are available.
        Some SMTP servers allow unauthenticated sending from trusted IPs.

        Args:
            server: The SMTP server connection to authenticate.

        Raises:
            smtplib.SMTPAuthenticationError: If authentication fails.
        """
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)


