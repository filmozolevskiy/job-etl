# Notifier Service

Extensible notification service for sending alerts and summaries through multiple channels (email, future: WhatsApp, Telegram, etc.).

## Overview

The notifier service provides a clean, extensible interface for sending notifications. It currently supports email via SMTP, with an architecture designed to easily add additional channels in the future.

## Architecture

### Core Components

- **`NotificationMessage`**: Structured message data (subject, text, HTML, metadata)
- **`NotificationChannel`**: Protocol interface for channel implementations
- **`Notifier`**: Orchestrator that sends messages through multiple channels
- **`EmailChannel`**: SMTP-based email implementation

### Design Principles

1. **Extensibility**: New channels can be added by implementing the `NotificationChannel` protocol
2. **Resilience**: Channel failures don't stop other channels from receiving the message
3. **Flexibility**: Supports both plain text and HTML content
4. **Configuration**: Environment-based configuration with Docker secrets support

## Usage

### Command Line Interface

```bash
python -m services.notifier.main \
    --subject "Daily Job-ETL Summary" \
    --text "Plain text message body" \
    --html "<h1>HTML message body</h1>" \
    --metadata '{"run_id": "12345"}'
```

### Programmatic Usage

```python
from services.notifier.base import NotificationMessage, Notifier
from services.notifier.email import EmailChannel

# Create email channel
email_channel = EmailChannel()

# Create notifier with channels
notifier = Notifier([email_channel])

# Send notification
message = NotificationMessage(
    subject="Test Notification",
    text="Plain text content",
    html="<h1>HTML content</h1>",
    metadata={"source": "test"}
)

notifier.notify(message)
```

### Airflow Integration

The notifier is integrated into the `jobs_etl_daily` DAG and automatically sends daily summaries after pipeline completion.

## Configuration

### Environment Variables

#### Required
- `SMTP_HOST`: SMTP server hostname (e.g., `smtp.gmail.com`)
- `SMTP_FROM`: Sender email address (e.g., `job-etl@example.com`)
- `NOTIFY_TO`: Comma-separated recipient email addresses (e.g., `user1@example.com,user2@example.com`)

#### Optional
- `SMTP_PORT`: SMTP server port (default: `587`)
- `SMTP_USER`: SMTP username for authentication (optional)
- `SMTP_PASSWORD`: SMTP password (optional; can use Docker secret instead)
- `SMTP_USE_TLS`: Enable TLS encryption (default: `true`)
- `SMTP_USE_SSL`: Use SSL instead of TLS (default: `false`)

### Docker Secrets

For production deployments, store the SMTP password in a Docker secret:

```bash
# Create secret file
echo "your-smtp-password" > secrets/notifications/smtp_password.txt
```

The service will automatically read from `/run/secrets/smtp_password` if `SMTP_PASSWORD` is not set.

## Examples

### Gmail SMTP

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_FROM="your-email@gmail.com"
export NOTIFY_TO="recipient@example.com"
export SMTP_USE_TLS="true"
# Set SMTP_PASSWORD or use Docker secret
```

### SendGrid SMTP

```bash
export SMTP_HOST="smtp.sendgrid.net"
export SMTP_PORT="587"
export SMTP_USER="apikey"
export SMTP_FROM="noreply@example.com"
export NOTIFY_TO="team@example.com"
export SMTP_USE_TLS="true"
# Set SMTP_PASSWORD to your SendGrid API key
```

### Local Development (MailHog)

```bash
export SMTP_HOST="localhost"
export SMTP_PORT="1025"
export SMTP_FROM="test@localhost"
export NOTIFY_TO="dev@localhost"
export SMTP_USE_TLS="false"
# No authentication needed for local MailHog
```

## Adding New Channels

To add a new notification channel (e.g., WhatsApp, Telegram):

1. Create a new file `services/notifier/whatsapp.py` (or similar)
2. Implement the `NotificationChannel` protocol:

```python
from .base import NotificationChannel, NotificationMessage

class WhatsAppChannel(NotificationChannel):
    def send(self, message: NotificationMessage) -> None:
        # Implement WhatsApp API call
        pass
```

3. Register the channel in `build_notifier()`:

```python
def build_notifier() -> Notifier:
    channels = [
        EmailChannel(),
        WhatsAppChannel(),  # Add new channel
    ]
    return Notifier(channels)
```

## Error Handling

- **Channel Failures**: If one channel fails, other channels still receive the message
- **Configuration Errors**: Missing required configuration raises `ValueError` with clear messages
- **SMTP Errors**: SMTP connection/auth errors are logged and propagated

## Testing

Run unit tests:

```bash
pytest tests/unit/services/test_notifier_email.py -v
```

Test coverage includes:
- TLS/SSL encryption modes
- HTML content handling
- Multiple recipients
- Configuration validation
- Error handling

## Type Hints

This service uses Python 3.10+ union syntax (`str | None`) for type hints. This is intentional as the project may upgrade from Python 3.9+ in the future. For consistency with other services that use `Optional[str]`, consider updating the project's Python version requirement or standardizing on one style.

## Dependencies

- `python-dotenv==1.0.0`: Environment variable management

## See Also

- [Airflow DAG Integration](../../airflow/dags/jobs_etl_daily.py)
- [Code Review](../../docs/features/notifier_email_REVIEW.md)

