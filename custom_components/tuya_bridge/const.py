"""Constants for Tuya Bridge integration."""

DOMAIN = "tuya_bridge"

CONF_API_KEY = "api_key"
CONF_API_SECRET = "api_secret"
CONF_API_REGION = "api_region"
CONF_API_DEVICE_ID = "api_device_id"

SCAN_INTERVAL_MINUTES = 30

# Tuya category -> tuya_local type hint
CATEGORY_TYPE_HINTS = {
    "cz": "smartplug",
    "pc": "smartplug",
    "dj": "rgbcw_lightbulb",
    "dd": "dimmer",
    "fwd": "dimmer",
    "xdd": "rgbcw_lightbulb",
    "wk": "thermostat",
    "wkf": "thermostat",
    "kt": "thermostat",
}

REGIONS = {
    "eu": "Europe",
    "us": "Americas",
    "cn": "China",
    "in": "India",
    "sg": "Singapore",
}

# Categories to skip (sub-devices, IR remotes — not directly controllable)
SKIP_CATEGORIES = {"infrared_ac", "qt"}
