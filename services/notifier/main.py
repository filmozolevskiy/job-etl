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

from .base import Notifier, NotificationMessage
from .email import EmailChannel


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
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
    channels = []
    # Always enable EmailChannel if SMTP is configured; raise early if not.
    channels.append(EmailChannel())
    return Notifier(channels)


def main() -> int:
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        notifier = build_notifier()
        metadata = None
        if args.metadata:
            try:
                metadata = json.loads(args.metadata)
            except json.JSONDecodeError:
                logger.warning('Invalid JSON for --metadata; ignoring')

        message = NotificationMessage(
            subject=args.subject,
            text=args.text,
            html=args.html,
            metadata=metadata,
        )

        notifier.notify(message)
        logger.info('Notification sent')
        return 0
    except Exception as e:
        logger.error(f'Failed to send notification: {e}', exc_info=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())


