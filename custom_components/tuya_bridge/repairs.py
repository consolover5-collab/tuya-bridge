"""Repair flows for Tuya Bridge — handles 'Add Locally' and 'Create Cloud Entity'."""

from __future__ import annotations

import logging
from typing import Any

import tinytuya
import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CATEGORY_TYPE_HINTS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TuyaBridgeRepairFlow(RepairsFlow):
    """Handle repair flow for a new unmanaged Tuya device."""

    def __init__(self, device_id: str) -> None:
        """Initialize with device_id."""
        super().__init__()
        self._device_id = device_id
        self._device_name: str = ""
        self._local_key: str = ""
        self._category: str = ""
        self._discovered_ip: str | None = None

    def _load_device_info(self) -> None:
        """Load device info from coordinator."""
        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            coordinator = entry_data.get("coordinator")
            if coordinator and coordinator.data and self._device_id in coordinator.data:
                info = coordinator.data[self._device_id]
                self._device_name = info.name
                self._local_key = info.local_key
                self._category = info.category
                return

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """First step — offer Add Locally or Create Cloud Entity."""
        self._load_device_info()

        if user_input is not None:
            action = user_input.get("action")
            if action == "add_local":
                return await self.async_step_discover()
            if action == "cloud_entity":
                return await self.async_step_cloud_stub()
            if action == "ignore":
                ir.async_delete_issue(self.hass, DOMAIN, f"new_device_{self._device_id}")
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="add_local"): vol.In(
                        {
                            "add_local": "Add locally (Tuya Local)",
                            "cloud_entity": "Create Cloud Entity",
                            "ignore": "Ignore this device",
                        }
                    ),
                }
            ),
            description_placeholders={
                "name": self._device_name,
                "device_id": self._device_id,
                "category": self._category,
            },
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Scan network for device IP."""
        if self._discovered_ip is None:
            self._discovered_ip = await self.hass.async_add_executor_job(
                self._scan_for_device
            )

        if user_input is not None:
            ip = user_input.get("host", "").strip()
            if ip:
                return await self._create_tuya_local_entry(ip)
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required("host", default=""): str,
                    }
                ),
                errors={"host": "invalid_ip"},
                description_placeholders={
                    "name": self._device_name,
                    "status": "Please enter a valid IP address",
                },
            )

        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=self._discovered_ip or ""): str,
                }
            ),
            description_placeholders={
                "name": self._device_name,
                "status": "Found!" if self._discovered_ip else "Not found — enter manually",
            },
        )

    async def async_step_cloud_stub(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Stub for Cloud Entity creation — coming soon."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="cloud_stub",
            data_schema=vol.Schema({}),
            description_placeholders={"name": self._device_name},
        )

    def _scan_for_device(self) -> str | None:
        """Scan local network for device using tinytuya UDP broadcast."""
        _LOGGER.info("Scanning network for device %s...", self._device_id)
        try:
            result = tinytuya.find_device(dev_id=self._device_id, timeout=18)
            if result and result.get("ip"):
                _LOGGER.info("Found device %s at %s", self._device_id, result["ip"])
                return result["ip"]
        except Exception:
            _LOGGER.exception("Network scan failed for %s", self._device_id)
        return None

    async def _create_tuya_local_entry(self, host: str) -> data_entry_flow.FlowResult:
        """Programmatically create a tuya_local config entry via its config flow."""
        try:
            # Step 1: Init flow
            result = await self.hass.config_entries.flow.async_init(
                "tuya_local", context={"source": "user"}
            )
            flow_id = result["flow_id"]

            # Step 2: Select manual mode
            result = await self.hass.config_entries.flow.async_configure(
                flow_id, {"setup_mode": "manual"}
            )

            # Step 3: Submit device details
            result = await self.hass.config_entries.flow.async_configure(
                flow_id,
                {
                    "device_id": self._device_id,
                    "host": host,
                    "local_key": self._local_key,
                    "protocol_version": "auto",
                    "poll_only": False,
                },
            )

            if result.get("type") == "abort":
                reason = result.get("reason", "unknown")
                _LOGGER.warning("tuya_local flow aborted: %s", reason)
                return self.async_abort(reason=f"tuya_local: {reason}")

            if result.get("step_id") == "select_type":
                # Step 4: Auto-select device type
                device_type = self._pick_device_type(result, self._category)
                result = await self.hass.config_entries.flow.async_configure(
                    flow_id, {"type": device_type}
                )

            if result.get("step_id") == "choose_entities":
                # Step 5: Set name
                result = await self.hass.config_entries.flow.async_configure(
                    flow_id, {"name": self._device_name}
                )

            if result.get("type") == "create_entry":
                _LOGGER.info(
                    "Successfully created tuya_local entry for %s", self._device_id
                )
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"new_device_{self._device_id}"
                )
                return self.async_create_entry(data={"result": "added_locally"})

            _LOGGER.warning("Unexpected flow result: %s", result)
            return self.async_abort(reason="unexpected_flow_result")

        except Exception:
            _LOGGER.exception("Failed to create tuya_local entry")
            return self.async_abort(reason="creation_failed")

    def _pick_device_type(self, flow_result: dict, category: str) -> str:
        """Pick the best device type from tuya_local's available options."""
        schema = flow_result.get("data_schema")
        options: list[str] = []

        if schema:
            for field in schema.get("schema", []):
                if field.get("name") == "type":
                    options = list(field.get("options", {}).keys())
                    break

        if not options:
            try:
                for key in flow_result["data_schema"].schema:
                    if hasattr(key, "schema") and key.schema == "type":
                        container = flow_result["data_schema"].schema[key]
                        if hasattr(container, "container"):
                            options = list(container.container.keys())
                        break
            except Exception:
                pass

        if not options:
            return ""

        # Try category hint
        hint = CATEGORY_TYPE_HINTS.get(category, "")
        if hint:
            for opt in options:
                if hint in opt:
                    return opt

        # Prefer energy monitoring variants
        for opt in options:
            if "energy" in opt:
                return opt

        return options[0]


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> TuyaBridgeRepairFlow:
    """Create repair flow for a Tuya Bridge issue."""
    device_id = ""
    if data:
        device_id = data.get("device_id", "")
    if not device_id:
        device_id = issue_id.replace("new_device_", "")
    return TuyaBridgeRepairFlow(device_id)
