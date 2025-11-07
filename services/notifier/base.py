from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class NotificationMessage:
    """
    A structured notification message.

    The `subject` is used for channels that support it (e.g., email),
    while `text` is a plain-text fallback. `html` is optional rich content.
    `metadata` can carry channel-agnostic context (e.g., run_id, counts).
    """

    subject: str
    text: str
    html: str | None = None
    metadata: Mapping[str, Any] | None = None


class NotificationChannel(Protocol):
    """
    Protocol for a notification channel implementation.

    Future channels (e.g., WhatsApp, Telegram) should implement this.
    """

    def send(self, message: NotificationMessage) -> None:
        """Send the message via this channel."""


class Notifier:
    """
    Orchestrates sending notifications to one or more channels.
    """

    def __init__(self, channels: Sequence[NotificationChannel]):
        self._channels = list(channels)

    def notify(self, message: NotificationMessage) -> None:
        """
        Send a notification message through all configured channels.

        Iterates through all registered channels and sends the message via each.
        If one channel fails, the error is logged and processing continues to
        the next channel, allowing partial success in multi-channel scenarios.

        Args:
            message: The notification message to send.

        Note:
            Failures in individual channels are logged but do not stop processing
            of other channels. This allows notifications to be sent through
            multiple channels even if one fails.
        """
        import logging
        logger = logging.getLogger(__name__)

        for channel in self._channels:
            try:
                channel.send(message)
            except Exception as e:
                channel_name = channel.__class__.__name__
                logger.error(
                    f"Channel {channel_name} failed to send notification: {e}",
                    exc_info=True
                )
                # Continue to next channel instead of raising


