"""
FastAPI App to Expose Viessmann OAuth2 Metrics for Prometheus
"""

import os
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from typing import Optional

from .viessmann_oauth import TokenStore, ViessmannOAuthService

AUTHORIZE_URL = "https://iam.viessmann-climatesolutions.com/idp/v3/authorize"
TOKEN_URL = "https://iam.viessmann-climatesolutions.com/idp/v3/token"

CLIENT_ID = os.environ["VIESSMANN_CLIENT_ID"]
CLIENT_SECRET = os.environ.get("VIESSMANN_CLIENT_SECRET")
REDIRECT_URI = os.environ["VIESSMANN_REDIRECT_URI"]
SCOPE = os.environ.get("VIESSMANN_SCOPE", "IoT")
CALLBACK_URL = os.environ.get("VIESSMANN_CALLBACK_URL", "/oauth/callback")
LOGIN_URL = os.environ.get("VIESSMANN_LOGIN_URL", "/oauth/login")
REFRESH_ACCESS_URL = os.environ.get("VIESSMANN_REFRESH_ACCESS_URL", "/oauth/refresh-access")
SUCCESS_URL = os.environ.get("VIESSMANN_SUCCESS_URL", "/success")
FAIL_URL = os.environ.get("VIESSMANN_FAIL_URL", "/fail")
DEBUG_STATUS_URL = os.environ.get("VIESSMANN_DEBUG_STATUS_URL", "/debug/token/status")
DEBUG_RAW_URL = os.environ.get("VIESSMANN_DEBUG_RAW_URL", "/debug/token/raw")
DEBUG_ROUTES_URL = os.environ.get("VIESSMANN_DEBUG_ROUTES_URL", "/debug/routes")
DEBUG_CONFIG_URL = os.environ.get("VIESSMANN_DEBUG_CONFIG_URL", "/debug/config")

TOKEN_STORE_PATH = Path(os.environ.get("VIESSMANN_TOKEN_STORE", "./viessmann_tokens.json"))

service = ViessmannOAuthService(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    authorize_url=AUTHORIZE_URL,
    token_url=TOKEN_URL,
    token_store=TokenStore(TOKEN_STORE_PATH),
)

@asynccontextmanager
async def lifespan(viessmann_prometheus: FastAPI):
    print("Registered routes based on lifespan:")
    for r in viessmann_prometheus.routes:
        methods = getattr(r, "methods", None)
        print(f"{r.path:40} {methods}")
    yield

viessmann_prometheus = FastAPI(title="Viessmann OAuth Backend", lifespan=lifespan)



@viessmann_prometheus.get("/health")
def health():
    return PlainTextResponse("ok", status_code=200)


@viessmann_prometheus.get(LOGIN_URL)
def login():
    """
    Endpoint for browser-based login to Viessmann developer.
    Should be initiated from a web browser.
    Mandatory to provide Viessmann OAuth2 API authentication.
    Viessmann refresh token is valid around 180 days.
    To renew refresh token, `offline_access` should be added to the scope.
    """
    url, _state = service.build_authorize_url()
    return RedirectResponse(url, status_code=302)


@viessmann_prometheus.get(CALLBACK_URL)
async def callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """ Endpoint to provide callback for vissman Oauth2 service
        mandatory to provide viessamnn authentification
        exposed endpoind shoud be registered as callback
        for Viessmann Developer portal Oauth2 API
    """
    if error:
        # Keep error message short (no secrets)
        msg = f"OAuth error: {error}"
        if error_description:
            msg += f"\n{error_description}"
        return PlainTextResponse(msg, status_code=400)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")

    try:
        await service.exchange_code_for_token(code=code, state=state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(SUCCESS_URL, status_code=302)


#ANCHOR - TBD status should be adjusted for status (success||fail) urls
@viessmann_prometheus.post(REFRESH_ACCESS_URL)
async def refresh():
    """  Endpoint to iniitate access token refresh
    """
    try:
        await service.refresh_access_token()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}


# ---- Debug routes (without sensitive information) ----
@viessmann_prometheus.get(DEBUG_STATUS_URL)
def debug_status():
    """
        Endpoint to show latest status of the token
    """
    store = service.token_store.load()
    return {
        "has_access_token": bool(store.get("access_token")),
        "has_refresh_token": bool(store.get("refresh_token")),
        "expires_in": store.get("expires_in"),
        "updated_at": store.get("updated_at"),
        "refresh_updated_at": store.get("refresh_updated_at"),
        "last_success": store.get("last_token_success"),
        "last_error": store.get("last_token_error"),
    }


@viessmann_prometheus.get(DEBUG_RAW_URL)
def debug_raw():
    # Endpoint fordebuging purpose
    return service.token_store.load()


@viessmann_prometheus.get(SUCCESS_URL)
def viessmann_success():
    """ Generic endpoint to show OAuth2 Login status """
    return HTMLResponse(
        "<h2>✅ Viessmann OAuth success</h2><p>You can close this window.</p>"
        f"<p><a href='LOGIN_URL'>Source</a></p>",
        status_code=200,
    )


@viessmann_prometheus.get(FAIL_URL)
def viessmann_fail(error: str = "", desc: str = ""):
    """ Generic endpoint to show OAuth2 Login status """
    # Error page to share error text.
    return HTMLResponse(
        f"<h2>❌ Viessmann OAuth failed</h2>"
        f"<p>error={error}</p><p>{desc}</p>"
        f"<p><a href='LOGIN_URL'>Try again</a></p>",
        status_code=200,
    )

@viessmann_prometheus.get(DEBUG_ROUTES_URL)
def show_routes():
    out = []
    for r in viessmann_prometheus.routes:
      out.append({"path": r.path, "methods": sorted(getattr(r, "methods", []) or [])})
    return JSONResponse(out)


@viessmann_prometheus.get(DEBUG_CONFIG_URL)
def get_config() :
    return JSONResponse(viessmann_prometheus.state.config)

def print_routes():
    print("Registered routes:")
    for r in viessmann_prometheus.routes:
        print(r.path, r.methods)
