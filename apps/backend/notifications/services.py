from .models import Notification


def create_notification(
    *,
    organization,
    event_type: str,
    title: str,
    message: str = "",
    link_path: str = "",
    recipient=None,
) -> Notification:
    """Persist an organization-scoped in-app notification."""
    return Notification.objects.create(
        organization=organization,
        recipient=recipient,
        event_type=event_type,
        title=title[:160],
        message=message,
        link_path=link_path[:255],
    )
