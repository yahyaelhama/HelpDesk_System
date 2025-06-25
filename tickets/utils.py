from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
import logging

# Get a logger
logger = logging.getLogger(__name__)

def send_ticket_created_email(request, ticket):
    """
    Send an email notification to the user when a ticket is created.
    """
    logger.info(f"Attempting to send ticket creation email for ticket #{ticket.id}")
    
    subject = f"{settings.HELPDESK_EMAIL_SUBJECT_PREFIX}Ticket #{ticket.id} Created"
    from_email = settings.HELPDESK_EMAIL_FROM
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
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
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
    from_email = settings.HELPDESK_EMAIL_FROM
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
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Successfully sent ticket resolution email for ticket #{ticket.id} to {to_email}")
    except Exception as e:
        logger.error(f"Error sending ticket resolution email for ticket #{ticket.id}: {str(e)}") 