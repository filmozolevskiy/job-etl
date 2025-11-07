"""
Notifier Service - Main Entry Point

CLI for sending notifications via configured channels. Currently supports
email (SMTP). Future channels (WhatsApp, Telegram) can be added by
implementing `NotificationChannel`.

Usage:
    python -m services.notifier.main --subject "Daily Job-ETL summary" \
        --text "..." [--html "..."]
"""

import argparse
import json
import logging
import sys

from dotenv import load_dotenv

from .base import NotificationMessage, Notifier
from .email import EmailChannel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the notifier CLI.

    Returns:
        argparse.Namespace: Parsed command-line arguments with the following attributes:
            - subject (str): Notification subject line (required)
            - text (str): Plain text message body (required)
            - html (str, optional): HTML message body
            - metadata (str, optional): JSON string containing additional context
            - verbose (bool): Enable debug-level logging

    Raises:
        SystemExit: If required arguments are missing or invalid.
    """
    parser = argparse.ArgumentParser(
        description='Send a notification via configured channels.'
    )
    parser.add_argument('--subject', required=True, help='Notification subject')
    parser.add_argument('--text', required=True, help='Plain text body')
    parser.add_argument('--html', required=False, help='HTML body')
    parser.add_argument('--metadata', required=False, help='JSON metadata for context')
    parser.add_argument('--verbose', action='store_true', help='Enable debug logging')
    return parser.parse_args()


def build_notifier() -> Notifier:
    """
    Build and configure a Notifier instance with available channels.

    Currently configures EmailChannel with SMTP settings from environment
    variables. The EmailChannel constructor will raise ValueError if required
    SMTP configuration is missing.

    Returns:
        Notifier: Configured notifier instance with email channel enabled.

    Raises:
        ValueError: If SMTP configuration is incomplete (missing SMTP_HOST,
            SMTP_FROM, or NOTIFY_TO).
    """
    channels = []
    # Always enable EmailChannel if SMTP is configured; raise early if not.
    channels.append(EmailChannel())
    return Notifier(channels)


def main() -> int:
    """
    Main entry point for the notifier CLI.

    Parses command-line arguments, builds a notifier instance, creates a
    notification message, and sends it through all configured channels.

    Returns:
        int: Exit code (0 for success, 2 for failure).

    Side Effects:
        - Sends notification via configured channels (e.g., email)
        - Logs success or failure messages
    """
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Build notifier with configured channels
        notifier = build_notifier()

        # Parse optional metadata JSON
        metadata = None
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError:
                logger.warning('Invalid JSON for --metadata; ignoring')

        # Create notification message
        message = NotificationMessage(
            subject=args.subject,
            text=args.text,
            html=args.html,
            metadata=metadata,
        )

        # Send notification through all channels
        notifier.notify(message)
        logger.info('Notification sent')
        return 0
    except Exception as e:
        logger.error(f'Failed to send notification: {e}', exc_info=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())


