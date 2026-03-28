"""DataUpdateCoordinator for Tuya Bridge — scans Tuya Cloud for unmanaged devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

import tinytuya
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_API_DEVICE_ID,
    CONF_API_KEY,
    CONF_API_REGION,
    CONF_API_SECRET,
    DOMAIN,
    SCAN_INTERVAL_MINUTES,
    SKIP_CATEGORIES,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TuyaDeviceInfo:
    """Info about a Tuya Cloud device."""

    device_id: str
    name: str
    category: str
    local_key: str
    sub: bool
    ip: str = ""


class TuyaBridgeCoordinator(DataUpdateCoordinator[dict[str, TuyaDeviceInfo]]):
    """Coordinator that fetches Tuya Cloud devices and finds unmanaged ones."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self._api_key = entry.data[CONF_API_KEY]
        self._api_secret = entry.data[CONF_API_SECRET]
        self._api_region = entry.data[CONF_API_REGION]
        self._api_device_id = entry.data[CONF_API_DEVICE_ID]

    def _get_cloud_devices(self) -> list[dict[str, Any]]:
        """Fetch devices from Tuya Cloud (blocking)."""
        cloud = tinytuya.Cloud(
            apiRegion=self._api_region,
            apiKey=self._api_key,
            apiSecret=self._api_secret,
            apiDeviceID=self._api_device_id,
        )
        result = cloud.getdevices(verbose=True)
        if isinstance(result, dict):
            return result.get("result", [])
        if isinstance(result, list):
            return result
        return []

    def _get_tuya_local_device_ids(self) -> set[str]:
        """Get device IDs already configured in tuya_local."""
        ids: set[str] = set()
        for entry in self.hass.config_entries.async_entries("tuya_local"):
            if entry.unique_id:
                ids.add(entry.unique_id)
            device_id = entry.data.get("device_id", "")
            if device_id:
                ids.add(device_id)
        return ids

    async def _async_update_data(self) -> dict[str, TuyaDeviceInfo]:
        """Fetch cloud devices and filter unmanaged ones."""
        raw_devices = await self.hass.async_add_executor_job(self._get_cloud_devices)
        existing_ids = self._get_tuya_local_device_ids()

        unmanaged: dict[str, TuyaDeviceInfo] = {}
        for dev in raw_devices:
            device_id = dev.get("id", "")
            category = dev.get("category", "")
            sub = dev.get("sub", False)

            if not device_id:
                continue
            if device_id in existing_ids:
                continue
            if category in SKIP_CATEGORIES:
                continue
            if sub:
                continue

            unmanaged[device_id] = TuyaDeviceInfo(
                device_id=device_id,
                name=dev.get("name", device_id),
                category=category,
                local_key=dev.get("local_key", dev.get("key", "")),
                sub=sub,
                ip=dev.get("ip", ""),
            )

        _LOGGER.info(
            "Tuya Bridge scan: %d cloud devices, %d in tuya_local, %d unmanaged",
            len(raw_devices),
            len(existing_ids),
            len(unmanaged),
        )
        return unmanaged
