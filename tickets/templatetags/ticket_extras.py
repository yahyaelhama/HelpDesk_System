from django import template
import os

register = template.Library()

@register.filter
def filename(value):
    return os.path.basename(value)

@register.filter
def get_status_class(status):
    """Return the appropriate Bootstrap class for a status value."""
    status_classes = {
        'new': 'bg-info',
        'in_progress': 'bg-primary',
        'pending': 'bg-warning',
        'resolved': 'bg-success',
        'closed': 'bg-secondary'
    }
    return status_classes.get(status, 'bg-secondary')

@register.filter
def get_priority_class(priority):
    """Return the appropriate Bootstrap class for a priority value."""
    priority_classes = {
        'low': 'bg-success',
        'medium': 'bg-info',
        'high': 'bg-warning',
        'urgent': 'bg-danger'
    }
    return priority_classes.get(priority, 'bg-secondary')

@register.filter
def hours_from_seconds(seconds):
    """Calculate hours from seconds."""
    return seconds // 3600

@register.filter
def minutes_from_seconds(seconds):
    """Calculate minutes from seconds after removing hours."""
    return (seconds % 3600) // 60 