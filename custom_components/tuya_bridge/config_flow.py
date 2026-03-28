"""Config flow for Tuya Bridge integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_DEVICE_ID,
    CONF_API_KEY,
    CONF_API_REGION,
    CONF_API_SECRET,
    DOMAIN,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)


def _find_seed_device_id(hass: HomeAssistant) -> str | None:
    """Find any device_id from existing tuya_local or tuya entries to use as API seed."""
    # Try tuya_local first
    for entry in hass.config_entries.async_entries("tuya_local"):
        device_id = entry.data.get("device_id", "")
        if device_id:
            return device_id

    # Try official tuya integration device registry
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    for device in dev_reg.devices.values():
        for identifier in device.identifiers:
            if identifier[0] == "tuya" and identifier[1]:
                return identifier[1]

    return None


async def _validate_credentials(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Validate Tuya Cloud credentials. Return None on success, error dict on failure."""
    import tinytuya

    def _test_cloud() -> bool:
        cloud = tinytuya.Cloud(
            apiRegion=data[CONF_API_REGION],
            apiKey=data[CONF_API_KEY],
            apiSecret=data[CONF_API_SECRET],
            apiDeviceID=data[CONF_API_DEVICE_ID],
        )
        result = cloud.getdevices()
        if isinstance(result, dict) and "Error" in result:
            return False
        return True

    try:
        valid = await hass.async_add_executor_job(_test_cloud)
        if not valid:
            return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Failed to connect to Tuya Cloud")
        return {"base": "cannot_connect"}

    return None


class TuyaBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tuya Bridge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — Tuya Cloud credentials."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            # Auto-fill device_id if not provided
            if not user_input.get(CONF_API_DEVICE_ID):
                seed = _find_seed_device_id(self.hass)
                if seed:
                    user_input[CONF_API_DEVICE_ID] = seed
                else:
                    errors = {"base": "no_devices"}
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._build_schema(),
                        errors=errors,
                    )

            errors_result = await _validate_credentials(self.hass, user_input)
            if errors_result is None:
                return self.async_create_entry(
                    title=f"Tuya Bridge ({user_input[CONF_API_REGION].upper()})",
                    data=user_input,
                )
            errors = errors_result

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(),
            errors=errors,
        )

    def _build_schema(self) -> vol.Schema:
        """Build form schema — hide device_id if we can auto-detect it."""
        seed = _find_seed_device_id(self.hass)

        if seed:
            # Device ID auto-detected, don't ask user
            return vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_API_SECRET): str,
                    vol.Required(CONF_API_REGION, default="eu"): vol.In(REGIONS),
                }
            )

        # No existing devices — need device_id from user
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Required(CONF_API_REGION, default="eu"): vol.In(REGIONS),
                vol.Required(CONF_API_DEVICE_ID): str,
            }
        )
