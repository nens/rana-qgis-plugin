from pathlib import Path

PLUGIN_NAME = "Rana"
RANA_API_VERSION_PREFIX = "v1-alpha"

RANA_SETTINGS_ENTRY = "Rana"
RANA_AUTHCFG_ENTRY = f"{RANA_SETTINGS_ENTRY}/authcfg"
RANA_TENANT_ENTRY = f"{RANA_SETTINGS_ENTRY}/tenant"
RANA_CLENUP_CACHE_ON_CLOSE_ENTRY = f"{RANA_SETTINGS_ENTRY}/cleanup_cache_on_close"
THREEDI_AUTHCFG_ENTRY = "threedi/authcfg"

COGNITO_AUTHENTICATION_ENDPOINT = "https://auth.lizard.net/oauth2/authorize"
COGNITO_TOKEN_ENDPOINT = "https://auth.lizard.net/oauth2/token"
COGNITO_USER_INFO_ENDPOINT = "https://auth.lizard.net/oauth2/userInfo"
COGNITO_LOGOUT_ENDPOINT = "https://auth.lizard.net/logout"

SUPPORTED_DATA_TYPES = {
    "vector": "vector",
    "raster": "raster",
    "threedi_schematisation": "Rana schematisation",
    "sqlite": "Schematisation database",
}

STYLE_DIR = Path(__file__).parent / "styles"

PROGRESS_COLOR_RUNNING = "#2196F3"  # blue
PROGRESS_COLOR_FINISHED = "#4CAF50"  # green
PROGRESS_COLOR_FAILED = "#F44336"  # red
