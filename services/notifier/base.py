from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any
from collections.abc import Mapping, Sequence


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
        for channel in self._channels:
            channel.send(message)


