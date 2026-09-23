"""Gmail OAuth2 Authorization and Token Management.

Handles generating the authorization URL (PKCE), persisting pending state,
exchanging code/redirect URL for tokens, and refreshing expired tokens.
"""

import os
import json
import logging
from typing import Optional, Tuple
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DEFAULT_CLIENT_SECRETS_FILE = "credentials/gmail_oauth_client.json"
DEFAULT_TOKEN_FILE = "credentials/gmail_token.json"
PENDING_STATE_FILE = "credentials/.gmail_oauth_pending.json"
REDIRECT_URI = "http://localhost"


def get_client_secrets_path(custom_path: Optional[str] = None) -> str:
    """Resolve client secrets file path."""
    path = custom_path or os.environ.get("GMAIL_CLIENT_SECRETS_FILE", DEFAULT_CLIENT_SECRETS_FILE)
    if not os.path.isabs(path):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        candidate = os.path.join(base_dir, path)
        if os.path.isfile(candidate):
            return candidate
    return path


def get_token_path(custom_path: Optional[str] = None) -> str:
    """Resolve token file path."""
    path = custom_path or os.environ.get("GMAIL_TOKEN_FILE", DEFAULT_TOKEN_FILE)
    if not os.path.isabs(path):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        return os.path.join(base_dir, path)
    return path


def get_pending_state_path() -> str:
    """Resolve pending OAuth state file path."""
    token_p = get_token_path()
    return os.path.join(os.path.dirname(token_p), ".gmail_oauth_pending.json")


def start_authorization(
    client_secrets_file: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Start the OAuth2 authorization flow.
    Generates authorization URL with PKCE and stores state and code_verifier on disk.
    
    Returns:
        (authorization_url, state)
    """
    secrets_file = get_client_secrets_path(client_secrets_file)
    if not os.path.isfile(secrets_file):
        raise FileNotFoundError(f"Gmail OAuth client secrets file not found: {secrets_file}")

    flow = InstalledAppFlow.from_client_secrets_file(
        secrets_file,
        SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    auth_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )

    # Save pending state and PKCE verifier securely
    pending_file = get_pending_state_path()
    os.makedirs(os.path.dirname(pending_file), exist_ok=True)
    with open(pending_file, "w") as f:
        json.dump(
            {
                "state": state,
                "code_verifier": flow.code_verifier,
                "client_secrets_file": secrets_file,
            },
            f,
        )
    os.chmod(pending_file, 0o600)

    return auth_url, state


def finish_authorization(
    response_url_or_code: str,
    token_file: Optional[str] = None,
) -> Credentials:
    """
    Complete the OAuth2 flow by exchanging authorization code or callback URL.
    Saves the authorized user credentials to credentials/gmail_token.json.
    """
    pending_file = get_pending_state_path()
    if not os.path.isfile(pending_file):
        raise ValueError("No pending OAuth flow found. Please run start_authorization first.")

    with open(pending_file, "r") as f:
        pending_data = json.load(f)

    saved_state = pending_data.get("state")
    code_verifier = pending_data.get("code_verifier")
    secrets_file = pending_data.get("client_secrets_file") or get_client_secrets_path()

    flow = InstalledAppFlow.from_client_secrets_file(
        secrets_file,
        SCOPES,
        state=saved_state,
        redirect_uri=REDIRECT_URI,
    )
    flow.code_verifier = code_verifier

    # Allow http://localhost callback in oauthlib
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    raw_input = response_url_or_code.strip()

    import urllib.parse
    parsed_url = urllib.parse.urlparse(raw_input)
    qs = urllib.parse.parse_qs(parsed_url.query)
    if "code" in qs:
        code_val = qs["code"][0]
        flow.fetch_token(code=code_val)
    elif "code=" in raw_input or raw_input.startswith(("http://", "https://")):
        flow.fetch_token(authorization_response=raw_input)
    else:
        flow.fetch_token(code=raw_input)

    creds = flow.credentials

    # Save credentials securely
    out_token = get_token_path(token_file)
    os.makedirs(os.path.dirname(out_token), exist_ok=True)
    with open(out_token, "w") as f:
        f.write(creds.to_json())
    os.chmod(out_token, 0o600)

    # Clean up pending state
    try:
        os.remove(pending_file)
    except OSError:
        pass

    logger.info(f"Gmail OAuth token successfully saved to {out_token}")
    return creds


def get_gmail_credentials(
    token_file: Optional[str] = None,
    client_secrets_file: Optional[str] = None,
) -> Optional[Credentials]:
    """
    Retrieve valid Gmail OAuth2 credentials.
    Refreshes the token automatically if expired.
    Returns None if not configured or not authorized yet.
    """
    token_path = get_token_path(token_file)
    if not os.path.isfile(token_path):
        return None

    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            os.chmod(token_path, 0o600)
            logger.info("Gmail OAuth token refreshed successfully.")
        return creds
    except Exception as exc:
        logger.error(f"Failed to load or refresh Gmail credentials: {exc}")
        return None
