import os
from unittest import mock

from services.notifier.base import NotificationMessage
from services.notifier.email import EmailChannel


def test_email_channel_sends_with_tls(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "noreply@test")
    monkeypatch.setenv("NOTIFY_TO", "a@test,b@test")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with mock.patch("smtplib.SMTP") as smtp_mock:
        channel = EmailChannel()
        msg = NotificationMessage(subject="s", text="t")
        channel.send(msg)

        assert smtp_mock.called
        instance = smtp_mock.return_value.__enter__.return_value
        assert instance.starttls.called
        assert instance.send_message.called


def test_email_channel_requires_minimum_config(monkeypatch):
    for var in ["SMTP_HOST", "SMTP_FROM", "NOTIFY_TO"]:
        monkeypatch.delenv(var, raising=False)

    try:
        EmailChannel()
        assert False, "Expected ValueError for missing config"
    except ValueError:
        pass


