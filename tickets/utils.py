from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
import logging

# Get a logger
logger = logging.getLogger(__name__)

# Explicit email settings
EMAIL_SETTINGS = {
    'host': 'smtp.gmail.com',
    'port': 587,
    'username': 'yahyaelhama@gmail.com',
    'password': 'rknc lxft acew avgs',
    'use_tls': True,
}

def get_email_connection():
    """
    Get an email connection with explicit settings.
    """
    return get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=EMAIL_SETTINGS['host'],
        port=EMAIL_SETTINGS['port'],
        username=EMAIL_SETTINGS['username'],
        password=EMAIL_SETTINGS['password'],
        use_tls=EMAIL_SETTINGS['use_tls'],
        fail_silently=False,
    )

def send_ticket_created_email(request, ticket):
    """
    Send an email notification to the user when a ticket is created.
    """
    logger.info(f"Attempting to send ticket creation email for ticket #{ticket.id}")
    
    subject = f"{settings.HELPDESK_EMAIL_SUBJECT_PREFIX}Ticket #{ticket.id} Created"
    from_email = EMAIL_SETTINGS['username']
    to_email = ticket.created_by.email
    
    # Skip if user has no email
    if not to_email:
        logger.warning(f"Cannot send email for ticket #{ticket.id}: User has no email address")
        return
    
    try:
        # Get the ticket URL
        protocol = 'https' if request.is_secure() else 'http'
        domain = get_current_site(request).domain
        ticket_url = f"{protocol}://{domain}{reverse('ticket_detail', args=[ticket.id])}"
        
        # Prepare context for templates
        context = {
            'ticket': ticket,
            'ticket_url': ticket_url,
        }
        
        # Render email templates
        html_content = render_to_string('emails/ticket_created.html', context)
        text_content = render_to_string('emails/ticket_created.txt', context)
        
        # Create and send email
        connection = get_email_connection()
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email], connection=connection)
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Successfully sent ticket creation email for ticket #{ticket.id} to {to_email}")
    except Exception as e:
        logger.error(f"Error sending ticket creation email for ticket #{ticket.id}: {str(e)}")


def send_ticket_resolved_email(request, ticket):
    """
    Send an email notification to the user when their ticket is resolved.
    """
    logger.info(f"Attempting to send ticket resolution email for ticket #{ticket.id}")
    
    subject = f"{settings.HELPDESK_EMAIL_SUBJECT_PREFIX}Ticket #{ticket.id} Resolved"
    from_email = EMAIL_SETTINGS['username']
    to_email = ticket.created_by.email
    
    # Skip if user has no email
    if not to_email:
        logger.warning(f"Cannot send email for ticket #{ticket.id}: User has no email address")
        return
    
    try:
        # Get the ticket URL
        protocol = 'https' if request.is_secure() else 'http'
        domain = get_current_site(request).domain
        ticket_url = f"{protocol}://{domain}{reverse('ticket_detail', args=[ticket.id])}"
        
        # Prepare context for templates
        context = {
            'ticket': ticket,
            'ticket_url': ticket_url,
        }
        
        # Render email templates
        html_content = render_to_string('emails/ticket_resolved.html', context)
        text_content = render_to_string('emails/ticket_resolved.txt', context)
        
        # Create and send email
        connection = get_email_connection()
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email], connection=connection)
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Successfully sent ticket resolution email for ticket #{ticket.id} to {to_email}")
    except Exception as e:
        logger.error(f"Error sending ticket resolution email for ticket #{ticket.id}: {str(e)}") 