"""Tuya Bridge — auto-bridge Tuya Cloud devices to Tuya Local."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type TuyaBridgeConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: TuyaBridgeConfigEntry) -> bool:
    """Set up Tuya Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    _LOGGER.info("Tuya Bridge loaded")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TuyaBridgeConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
