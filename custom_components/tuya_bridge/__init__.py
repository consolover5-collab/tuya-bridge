"""Tuya Bridge — auto-bridge Tuya Cloud devices to Tuya Local."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .coordinator import TuyaBridgeCoordinator

_LOGGER = logging.getLogger(__name__)

type TuyaBridgeConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: TuyaBridgeConfigEntry) -> bool:
    """Set up Tuya Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TuyaBridgeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # Create repair issues for unmanaged devices
    _create_issues(hass, coordinator)

    # Listen for future updates
    coordinator.async_add_listener(lambda: _create_issues(hass, coordinator))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TuyaBridgeConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def _create_issues(hass: HomeAssistant, coordinator: TuyaBridgeCoordinator) -> None:
    """Create or update repair issues for unmanaged devices."""
    if not coordinator.data:
        return

    ignored: set[str] = set(coordinator.config_entry.options.get("ignored_devices", []))

    for device_id, device_info in coordinator.data.items():
        if device_id in ignored:
            continue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"new_device_{device_id}",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="new_device_found",
            translation_placeholders={
                "name": device_info.name,
                "category": device_info.category,
                "device_id": device_id,
            },
            data={"device_id": device_id},
        )
