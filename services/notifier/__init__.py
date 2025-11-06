"""
Notifications microservice package.

Provides an extensible interface for sending notifications through
various channels (email, messaging apps, etc.).
"""

from .base import NotificationMessage, NotificationChannel, Notifier

__all__ = [
    "NotificationMessage",
    "NotificationChannel",
    "Notifier",
]


