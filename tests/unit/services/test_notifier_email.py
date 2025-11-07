from unittest import mock

from services.notifier.base import NotificationMessage, Notifier
from services.notifier.email import EmailChannel


def test_email_channel_sends_with_tls(monkeypatch):
    """Test email channel sends with TLS encryption."""
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


def test_email_channel_sends_with_ssl(monkeypatch):
    """Test email channel sends with SSL encryption."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_FROM", "noreply@test")
    monkeypatch.setenv("NOTIFY_TO", "a@test")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with mock.patch("smtplib.SMTP_SSL") as smtp_mock:
        channel = EmailChannel()
        msg = NotificationMessage(subject="s", text="t")
        channel.send(msg)

        assert smtp_mock.called
        instance = smtp_mock.return_value.__enter__.return_value
        assert instance.send_message.called


def test_email_channel_sends_html_content(monkeypatch):
    """Test email channel sends HTML content correctly."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "noreply@test")
    monkeypatch.setenv("NOTIFY_TO", "a@test")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with mock.patch("smtplib.SMTP") as smtp_mock:
        channel = EmailChannel()
        msg = NotificationMessage(
            subject="Test",
            text="Plain text",
            html="<h1>HTML content</h1>"
        )
        channel.send(msg)

        assert smtp_mock.called
        instance = smtp_mock.return_value.__enter__.return_value
        assert instance.send_message.called
        # Verify email message was created with HTML
        call_args = instance.send_message.call_args
        email_msg = call_args[0][0]
        assert email_msg.get_content_type() == "multipart/alternative"


def test_email_channel_multiple_recipients(monkeypatch):
    """Test email channel handles multiple recipients correctly."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM", "noreply@test")
    monkeypatch.setenv("NOTIFY_TO", "a@test, b@test, c@test")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    with mock.patch("smtplib.SMTP") as smtp_mock:
        channel = EmailChannel()
        assert len(channel.recipients) == 3
        assert "a@test" in channel.recipients
        assert "b@test" in channel.recipients
        assert "c@test" in channel.recipients

        msg = NotificationMessage(subject="s", text="t")
        channel.send(msg)

        assert smtp_mock.called
        instance = smtp_mock.return_value.__enter__.return_value
        assert instance.send_message.called


def test_email_channel_invalid_port(monkeypatch):
    """Test email channel raises ValueError for invalid SMTP_PORT."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_PORT", "invalid")
    monkeypatch.setenv("SMTP_FROM", "noreply@test")
    monkeypatch.setenv("NOTIFY_TO", "a@test")

    try:
        EmailChannel()
        assert False, "Expected ValueError for invalid SMTP_PORT"
    except ValueError as e:
        assert "SMTP_PORT must be numeric" in str(e)


def test_email_channel_requires_minimum_config(monkeypatch):
    """Test email channel requires minimum configuration."""
    for var in ["SMTP_HOST", "SMTP_FROM", "NOTIFY_TO"]:
        monkeypatch.delenv(var, raising=False)

    try:
        EmailChannel()
        assert False, "Expected ValueError for missing config"
    except ValueError:
        pass


def test_notifier_multiple_channels_continues_on_failure(monkeypatch):
    """Test Notifier continues to next channel if one fails."""
    import logging
    logging.basicConfig(level=logging.ERROR)

    # Create a mock channel that fails
    class FailingChannel:
        def send(self, message):
            raise Exception("Channel failed")

    # Create a mock channel that succeeds
    class SuccessChannel:
        def __init__(self):
            self.sent = False
        def send(self, message):
            self.sent = True

    success_channel = SuccessChannel()
    notifier = Notifier([FailingChannel(), success_channel])
    msg = NotificationMessage(subject="Test", text="Test")

    # Should not raise, and second channel should still be called
    notifier.notify(msg)
    assert success_channel.sent, "Second channel should have been called despite first failure"


