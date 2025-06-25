import os
import sys
import django

print("Starting email test...")

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helpdesk_project.settings')
django.setup()

from django.core.mail import get_connection, EmailMessage

# Explicitly define email settings
email_settings = {
    'host': 'smtp.gmail.com',
    'port': 587,
    'username': 'yahyaelhama@gmail.com',
    'password': 'rknc lxft acew avgs',
    'use_tls': True,
}

print(f"Using email settings:")
print(f"  Host: {email_settings['host']}")
print(f"  Port: {email_settings['port']}")
print(f"  Username: {email_settings['username']}")
print(f"  Use TLS: {email_settings['use_tls']}")

try:
    # Create a connection with explicit settings
    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=email_settings['host'],
        port=email_settings['port'],
        username=email_settings['username'],
        password=email_settings['password'],
        use_tls=email_settings['use_tls'],
        fail_silently=False,
    )
    
    # Create and send the email
    email = EmailMessage(
        subject='Test Email from Django Helpdesk',
        body='This is a test email from the Django Helpdesk system.',
        from_email=email_settings['username'],
        to=[email_settings['username']],
        connection=connection,
    )
    
    # Send the email
    result = email.send()
    print(f"Email sent successfully! Result: {result}")
except Exception as e:
    print(f"Error sending email: {e}")
    sys.exit(1)

print("Email test completed.") 