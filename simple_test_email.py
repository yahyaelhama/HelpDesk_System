import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email configuration
smtp_server = "smtp.gmail.com"
port = 587
sender_email = "yahyaelhama@gmail.com"  # Replace with your Gmail address
password = "rknc lxft acew avgs"  # Replace with your App Password
receiver_email = "yahyaelhama@gmail.com"  # Send to yourself for testing

print(f"Testing email with:")
print(f"  SMTP Server: {smtp_server}")
print(f"  Port: {port}")
print(f"  Sender: {sender_email}")
print(f"  Receiver: {receiver_email}")

try:
    # Create a multipart message
    message = MIMEMultipart()
    message["Subject"] = "Test Email from Python Script"
    message["From"] = sender_email
    message["To"] = receiver_email

    # Add body to email
    body = "This is a test email sent from Python script to test SMTP functionality."
    message.attach(MIMEText(body, "plain"))

    # Create SMTP session
    print("Creating SMTP session...")
    server = smtplib.SMTP(smtp_server, port)
    server.ehlo()  # Can be omitted
    
    # Start TLS encryption
    print("Starting TLS...")
    server.starttls()
    server.ehlo()  # Can be omitted
    
    # Login to server
    print("Logging in...")
    server.login(sender_email, password)
    
    # Send email
    print("Sending email...")
    text = message.as_string()
    server.sendmail(sender_email, receiver_email, text)
    
    # Close session
    server.quit()
    
    print("Email sent successfully!")
except Exception as e:
    print(f"Error: {e}") 