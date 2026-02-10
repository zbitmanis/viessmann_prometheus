# viessmann_oauth.py

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import base64
import hashlib
import secrets
import logging
import httpx


from .token_store import TokenStore
from .utils import now_ts

logger = logging.getLogger(__name__)

@dataclass
class ViessmannOAuthService:
    """
    Viessmann Oauth service class used to manage auth and request tokens
    """
    client_id: str
    redirect_uri: str
    scope: str
    authorize_url: str
    token_url: str
    token_store: TokenStore
    client_secret: Optional[str] = None

    # In-memory valid states (ok for single instance)
    valid_states: set[str] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.valid_states is None:
            self.valid_states = set()

    def build_authorize_url(self) -> Tuple[str, str]:
        """
        Returns: (authorize_url, state)
        Persists PKCE verifier keyed by state (simple single-user approach)
        """
        state = secrets.token_urlsafe(24)
        self.valid_states.add(state)

        verifier = self.pkce_code_verifier()
        challenge = self.pkce_code_challenge_s256(verifier)

        store = self.token_store.load()
        store['pkce'] = {'state': state, 'code_verifier': verifier, 'created_at': now_ts()}
        self.token_store.save(store)

        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': self.scope,
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        }
        url = str(httpx.URL(self.authorize_url).copy_merge_params(params))
        return url, state

    async def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for tokens, updates store.
        """
        if state not in self.valid_states:
            raise ValueError('Invalid state')

        self.valid_states.remove(state)

        store = self.token_store.load()
        pkce = store.get('pkce') or {}
        if pkce.get('state') != state or not pkce.get('code_verifier'):
            raise ValueError('Missing PKCE verifier for state')

        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'code': code,
            'code_verifier': pkce['code_verifier'],
        }
        if self.client_secret:
            data['client_secret'] = self.client_secret

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                self.token_url,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            )

        if r.status_code != 200:
            store['last_token_error'] = {'reason': r.text, 'time': now_ts()}
            self.token_store.save(store)
            raise ValueError(f'Token exchange failed: {r.status_code}')

        token_json = r.json()
        store = self.handle_token_response(token_json, store)
        store.pop('pkce', None)
        self.token_store.save(store)
        return token_json

    def handle_token_response(self, token_response: Dict[str, Any], store: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rotation-safe storage:
        - Always overwrite access_token
        - Overwrite refresh_token ONLY if returned
        - Persist metadata + last success/error
        """
        access = token_response.get('access_token')
        if not access:
            store['last_token_error'] = {'reason': 'missing access_token', 'time': now_ts()}
            return store

        store['access_token'] = access
        store['token_type'] = token_response.get('token_type', 'Bearer')
        store['expires_in'] = token_response.get('expires_in')
        store['scope'] = token_response.get('scope')
        store['updated_at'] = now_ts()

        rt = token_response.get('refresh_token')
        if rt:
            store['refresh_token'] = rt
            store['refresh_updated_at'] = now_ts()

        store['last_token_success'] = {'time': now_ts(), 'refresh_rotated': bool(rt)}
        store.pop('last_token_error', None)
        return store

    def pkce_code_verifier(self) -> str:
        """Provide urlsafe pkce token
        """
        return secrets.token_urlsafe(64)

    def pkce_code_challenge_s256(self, verifier: str) -> str:
        """ Provides Proof of Key Code Exchange extension required for Viessmann
            OAuth2 API verification
            more details https://blog.postman.com/what-is-pkce/
            alternative
            export VIESSMANN_CODE_CHALLENGE='$(printf '%s' '${VIESSMANN_CODE_VERIFIER}' \
             | openssl dgst -sha256 -binary \
             | openssl base64 -A \
             | tr '+/' '-_' \
         | tr -d '=')'
        """
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Headless/M2M: refresh access token using stored refresh token
        """
        store = self.token_store.load()
        rt = store.get('refresh_token')
        if not rt:
            raise ValueError('No refresh_token stored')

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'refresh_token': rt,
        }
        if self.client_secret:
            data['client_secret'] = self.client_secret

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                self.token_url,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            )

        if r.status_code != 200:
            store['last_token_error'] = {'reason': r.text, 'time': now_ts()}
            self.token_store.save(store)
            raise ValueError(f'Refresh failed: {r.status_code}')

        token_json = r.json()
        store = self.handle_token_response(token_json, store)
        self.token_store.save(store)
        return token_json
