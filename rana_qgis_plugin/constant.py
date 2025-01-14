from urllib.parse import quote

PLUGIN_NAME = "Rana"
RANA_SETTINGS_ENTRY = "Rana"
RANA_AUTHCFG_ENTRY = f"{RANA_SETTINGS_ENTRY}/authcfg"
RANA_TENANT_ENTRY = f"{RANA_SETTINGS_ENTRY}/tenant"
THREEDI_AUTHCFG_ENTRY = "threedi/authcfg"

COGNITO_CLIENT_ID = "250mkcukj5tn6lblsd6ka42c0a"
COGNITO_AUTHENTICATION_ENDPOINT = "https://auth.lizard.net/oauth2/authorize"
COGNITO_TOKEN_ENDPOINT = "https://auth.lizard.net/oauth2/token"
COGNITO_USER_INFO_ENDPOINT = "https://auth.lizard.net/oauth2/userInfo"
COGNITO_LOGOUT_ENDPOINT = "https://auth.lizard.net/logout"

BASE_URL = "https://www.ranawaterintelligence.com"
API_URL = f"{BASE_URL}/v1-alpha"
LOGOUT_REDIRECT_URI = f"{BASE_URL}/auth/callback/cognito/logout"
LOGOUT_REDIRECT_URI_ENCODED = quote(LOGOUT_REDIRECT_URI, safe="")
LOGOUT_URL = f"{COGNITO_LOGOUT_ENDPOINT}?client_id={COGNITO_CLIENT_ID}&logout_uri={LOGOUT_REDIRECT_URI_ENCODED}"
