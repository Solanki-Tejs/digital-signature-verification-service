import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

sender_email = os.getenv("EMAIL")
app_password = os.getenv("APP_PASSWORD")

def send_registration_email(to_email, full_name, reference_id):

    subject = "Registration Successful - Glyph"

    body = f"""
    Hello {full_name},

    You have been successfully registered with Glyph, a Digital Signature Verification System.

    Your Reference ID is:
    {reference_id}

    Please keep this reference ID safe for future use.

    If you did not initiate this registration, please contact support.

    Regards,
    Team Glyph
    """

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)

    except Exception as e:
        print("Email sending failed:", str(e))