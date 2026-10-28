"""
LinkedIn OAuth 2.0 Authorization Flow Helper for Automa.
Handles Authorization Code grant, token exchange, and Person URN retrieval.
"""

from __future__ import annotations
import logging
import os
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from dotenv import set_key
from automa.config import BASE_DIR, get_settings

logger = logging.getLogger("automa.publishers.linkedin_oauth")

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; background: #0B0F19; color: #F3F4F6; text-align: center; padding: 50px;">
                    <h1 style="color: #34D399;">Authentication Successful!</h1>
                    <p>LinkedIn has authorized Automa. You may close this browser tab and return to the terminal.</p>
                </body>
                </html>
            """)
        else:
            OAuthCallbackHandler.error = params.get("error_description", ["Unknown OAuth Error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <body style="font-family: sans-serif; background: #0B0F19; color: #F87171; text-align: center; padding: 50px;">
                    <h1>Authentication Failed</h1>
                    <p>{OAuthCallbackHandler.error}</p>
                </body>
                </html>
            """.encode("utf-8"))


def run_linkedin_auth_flow(
    client_id: str,
    client_secret: str,
    redirect_uri: str = "http://localhost:8000/callback",
    port: int = 8000,
) -> Tuple[str, str]:
    """
    Executes the OAuth 2.0 flow:
    1. Opens browser to LinkedIn login.
    2. Receives authorization code on local port.
    3. Exchanges code for access token.
    4. Fetches User Person URN.
    5. Saves credentials to .env file.
    """
    scope = "w_member_social openid profile email"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": "automa_auth_state",
    }
    login_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n" + "=" * 65)
    print(" LINKEDIN OAUTH 2.0 AUTHORIZATION HELPER")
    print("=" * 65)
    print(" 1. Ensure your LinkedIn App has this Redirect URL added:")
    print(f"    --> {redirect_uri}")
    print("    (In LinkedIn Developer Portal -> Your App -> 'Auth' tab -> 'OAuth 2.0 settings')")
    print("\n 2. Ensure your app has requested the 'Share on LinkedIn' and")
    print("    'Sign In with LinkedIn using OpenID Connect' products under the 'Products' tab.")
    print("-" * 65)
    print(" Opening browser for authorization:")
    print(f" {login_url}\n")

    webbrowser.open(login_url)

    # Start local server to capture redirect
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.error = None

    print(f" Waiting for callback on {redirect_uri} ...")
    server.handle_request()

    if OAuthCallbackHandler.error:
        raise RuntimeError(f"LinkedIn OAuth Error: {OAuthCallbackHandler.error}")

    auth_code = OAuthCallbackHandler.auth_code
    if not auth_code:
        raise RuntimeError("No authorization code received from LinkedIn.")

    print(" Authorization code received. Exchanging for access token...")

    # Exchange code for access token
    token_resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if token_resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed: HTTP {token_resp.status_code} - {token_resp.text}")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token found in response: {token_data}")

    print(" Access token acquired. Fetching Member URN...")

    # Fetch User Info to get Person URN
    userinfo_resp = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )

    person_urn = ""
    if userinfo_resp.status_code == 200:
        u_data = userinfo_resp.json()
        sub = u_data.get("sub")
        if sub:
            person_urn = f"urn:li:person:{sub}"
            print(f" Member identified: {u_data.get('name', 'User')} ({person_urn})")
    else:
        # Fallback to legacy me endpoint
        me_resp = requests.get(
            "https://api.linkedin.com/v2/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if me_resp.status_code == 200:
            m_data = me_resp.json()
            person_id = m_data.get("id")
            if person_id:
                person_urn = f"urn:li:person:{person_id}"
                print(f" Member URN identified: {person_urn}")

    if not person_urn:
        print(" Warning: Could not automatically detect Member Person URN.")
        person_urn = "urn:li:person:UNKNOWN"

    # Save to .env
    env_file = BASE_DIR / ".env"
    set_key(str(env_file), "LINKEDIN_ACCESS_TOKEN", access_token)
    set_key(str(env_file), "LINKEDIN_PERSON_URN", person_urn)

    print("\n Successfully updated .env with:")
    print("  - LINKEDIN_ACCESS_TOKEN")
    print(f"  - LINKEDIN_PERSON_URN={person_urn}")
    print("=" * 65 + "\n")

    return access_token, person_urn
