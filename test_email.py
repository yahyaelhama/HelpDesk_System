import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helpdesk_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("Starting email test...")

# Send a test email
try:
    result = send_mail(
        subject='Test Email from Django Helpdesk',
        message='This is a test email from the Django Helpdesk system.',
        from_email=settings.HELPDESK_EMAIL_FROM,
        recipient_list=['test@example.com'],
        fail_silently=False,
    )
    print(f"Email sent successfully! Result: {result}")
except Exception as e:
    print(f"Error sending email: {e}")
    
print("Email test completed.")
print("Emails are being output to the console.") 