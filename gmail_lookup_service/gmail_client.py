from __future__ import annotations

import os

from gmail_lookup_service.app_paths import get_credentials_path, get_token_path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

DEFAULT_CREDENTIALS_PATH = str(get_credentials_path())
DEFAULT_TOKEN_PATH = str(get_token_path())


def get_gmail_service(
    credentials_path: str = DEFAULT_CREDENTIALS_PATH,
    token_path: str = DEFAULT_TOKEN_PATH,
):
    creds: Optional[Credentials] = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service


def _header_value(headers: List[Dict[str, str]], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def search_messages(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    service = get_gmail_service()

    resp = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    messages = resp.get("messages", [])
    results: List[Dict[str, str]] = []

    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue

        detail = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        headers = detail.get("payload", {}).get("headers", [])
        subject = _header_value(headers, "Subject")
        sender = _header_value(headers, "From")
        date = _header_value(headers, "Date")
        snippet = detail.get("snippet", "")

        results.append(
            {
                "subject": subject,
                "from": sender,
                "date": date,
                "snippet": snippet,
                "link": f"https://mail.google.com/mail/u/0/#inbox/{msg_id}",
            }
        )

    return results


def test_search():
    query = 'in:inbox ("5551234567")'
    results = search_messages(query, max_results=5)
    return results


if __name__ == "__main__":
    print("Running Gmail test search...")
    results = test_search()
    print(f"Results: {len(results)}")
    for item in results:
        print("-", item.get("subject"), "|", item.get("from"))
