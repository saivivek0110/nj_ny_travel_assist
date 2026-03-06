"""
Email tools for Travel Agent
Implements Gmail sending for travel recommendations
"""
import os
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain.tools import tool
from config.settings import Config

# Gmail API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]


def is_email_configured() -> bool:
    """Returns True if Gmail OAuth credentials or token file exist."""
    return os.path.exists(Config.GMAIL_TOKEN_PATH) or os.path.exists(Config.GMAIL_CREDENTIALS_PATH)


def get_gmail_service():
    """
    Internal helper: Authenticates using token.json and returns Gmail service.
    Handles automatic token refreshing.
    """
    creds = None

    if os.path.exists(Config.GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(Config.GMAIL_TOKEN_PATH, SCOPES)

    # Refresh if expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Token expired, refreshing...")
            creds.refresh(Request())
        else:
            raise Exception(
                f"❌ {Config.GMAIL_TOKEN_PATH} not found or invalid. "
                "Please run setup_auth.py first to authenticate Gmail."
            )

    return build('gmail', 'v1', credentials=creds)


@tool
def send_email(subject: str, body: str, to_email: str) -> str:
    """
    Sends an email using Gmail account via OAuth.

    Args:
        subject: Email subject line
        body: Email body content (supports HTML)
        to_email: Recipient email address

    Returns:
        Success message with email ID or error message
    """
    if not is_email_configured():
        msg = "[Email skipped: Gmail not configured — run setup_auth.py to enable]"
        print(f"⚠️  {msg}")
        return msg

    try:
        service = get_gmail_service()
        print(f"📧 Preparing email to: {to_email}...")

        # Create message
        message = MIMEText(body, 'html')
        message['to'] = to_email
        message['subject'] = subject

        # Encode message for Gmail API
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_body = {'raw': raw_message}

        # Send email
        sent_message = service.users().messages().send(userId="me", body=send_body).execute()
        print(f"✅ Email sent successfully! ID: {sent_message['id']}")
        return f"✅ Email sent successfully to {to_email}! Message ID: {sent_message['id']}"

    except Exception as e:
        error_msg = f"❌ Failed to send email: {str(e)}"
        print(error_msg)
        return error_msg


@tool
def check_last_sent_email() -> str:
    """
    Checks the last email sent from the account to verify it was sent successfully.
    Useful for debugging and confirmation.

    Returns:
        Information about the last sent email
    """
    try:
        service = get_gmail_service()
        # List recent sent messages
        results = service.users().messages().list(
            userId='me',
            labelIds=['SENT'],
            maxResults=1
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            return "ℹ️ No sent emails found."

        # Get details of the most recent email
        message = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
        headers = message['payload']['headers']

        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        to = next((h['value'] for h in headers if h['name'] == 'To'), "Unknown Recipient")
        date = next((h['value'] for h in headers if h['name'] == 'Date'), "Unknown Date")

        return f"""✅ Last Sent Email Verified:
To: {to}
Subject: {subject}
Date: {date}
Message ID: {messages[0]['id']}"""

    except Exception as e:
        return f"❌ Failed to check sent emails: {str(e)}"
