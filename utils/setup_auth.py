#!/usr/bin/env python3
"""
Gmail Authentication Setup
Generates credentials.json and token.json for Gmail API access

Before running this script:
1. Go to https://console.cloud.google.com/
2. Create a new project named "Travel Agent"
3. Enable Gmail API for this project
4. Create OAuth 2.0 credentials (Desktop application)
5. Download the credentials as credentials.json
6. Place credentials.json in this directory
7. Run this script to generate token.json
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config.settings import Config

# Gmail API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]


def setup_gmail_auth():
    """Setup Gmail OAuth authentication"""
    print("\n" + "=" * 60)
    print("📧 GMAIL AUTHENTICATION SETUP")
    print("=" * 60)

    credentials_file = Config.GMAIL_CREDENTIALS_PATH
    token_file = Config.GMAIL_TOKEN_PATH

    print(f"\n🔍 Looking for credentials at: {credentials_file}")

    if not os.path.exists(credentials_file):
        print(f"\n❌ Error: {credentials_file} not found!")
        print("\nTo set up Gmail authentication:")
        print("1. Go to: https://console.cloud.google.com/")
        print("2. Create a new project: 'Travel Agent'")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download credentials as 'credentials.json'")
        print("6. Place it in this directory")
        print("7. Run this script again\n")
        return False

    print(f"✅ Found credentials.json\n")

    try:
        # Create flow from credentials
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file,
            scopes=SCOPES
        )

        # Run local server for user authentication
        print("🔐 Starting authentication flow...")
        print("A browser window will open for you to authorize access.\n")
        creds = flow.run_local_server(port=8080)

        # Save credentials
        with open(token_file, 'w') as token:
            import json
            json.dump({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
            }, token)

        print(f"✅ Authentication successful!")
        print(f"✅ Token saved to: {token_file}\n")
        print("=" * 60)
        print("You can now use the Travel Agent to send emails!")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"❌ Authentication failed: {e}\n")
        return False


if __name__ == "__main__":
    success = setup_gmail_auth()
    sys.exit(0 if success else 1)
