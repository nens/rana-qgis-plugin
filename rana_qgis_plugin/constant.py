PLUGIN_NAME = "Rana"

RANA_SETTINGS_ENTRY = "Rana"
RANA_AUTHCFG_ENTRY = f"{RANA_SETTINGS_ENTRY}/authcfg"
RANA_TENANT_ENTRY = f"{RANA_SETTINGS_ENTRY}/tenant"
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
