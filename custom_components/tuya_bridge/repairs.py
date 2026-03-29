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
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectOptionDict

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
        self._scan_results: dict[str, dict] | None = None
        self._auto_failed: bool = False

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
                    vol.Required("action", default="add_local"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="add_local", label="Add locally (Tuya Local)"),
                                SelectOptionDict(value="cloud_entity", label="Create Cloud Entity"),
                                SelectOptionDict(value="ignore", label="Ignore this device"),
                            ]
                        )
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
        """UDP scan → auto-connect if found, pick from list, or manual IP."""
        # User submitted the pick/manual form
        if user_input is not None:
            ip = user_input.get("host", "").strip()
            if not ip:
                return self._show_pick_form(error="invalid_ip")
            result = await self._create_tuya_local_entry(ip)
            if str(result.get("type", "")) != "abort":
                return result
            # Connection failed — show form again with error
            return self._show_pick_form(error="connection_failed")

        # First visit: full network scan
        if self._scan_results is None:
            self._scan_results = await self.hass.async_add_executor_job(
                self._scan_network
            )

        # Exact match by device_id → auto-connect
        if self._discovered_ip and not self._auto_failed:
            _LOGGER.info(
                "Auto-connecting %s at %s", self._device_id, self._discovered_ip,
            )
            result = await self._create_tuya_local_entry(self._discovered_ip)
            if str(result.get("type", "")) != "abort":
                return result
            _LOGGER.warning("Auto-connect to %s failed", self._discovered_ip)
            self._auto_failed = True

        # Show picker: other devices found or manual entry
        return self._show_pick_form()

    def _show_pick_form(
        self, error: str | None = None,
    ) -> data_entry_flow.FlowResult:
        """Show form to pick from discovered devices or enter IP manually."""
        errors = {}
        if error:
            errors["host"] = error

        # Build options from scan results (keyed by device_id via byID=True)
        managed_ids = set()
        for entry in self.hass.config_entries.async_entries("tuya_local"):
            did = entry.data.get("device_id", "")
            if did:
                managed_ids.add(did)

        options: list[SelectOptionDict] = []
        default_ip = self._discovered_ip or ""
        if self._scan_results:
            for dev_id, info in self._scan_results.items():
                # dev_id may be real device_id (UDP) or IP (TCP fallback)
                real_id = info.get("id", "") or dev_id
                if real_id in managed_ids:
                    continue
                ip = info.get("ip", "") or dev_id
                if not ip:
                    continue
                ver = info.get("version", "?")
                origin = info.get("origin", "udp")
                origin_tag = "" if origin != "tcp_scan" else " [tcp]"
                if real_id == self._device_id:
                    label = f"✓ {ip} — THIS DEVICE (...{real_id[-8:]}, v{ver})"
                elif real_id and real_id != ip:
                    label = f"{ip} — ...{real_id[-8:]} v{ver}{origin_tag}"
                else:
                    label = f"{ip} — unknown device{origin_tag}"
                options.append(SelectOptionDict(value=ip, label=label))

        target_found = self._discovered_ip is not None

        if options:
            if target_found:
                status = f"Device found at {self._discovered_ip} — confirm below"
            else:
                status = f"Target device not found on network — select another or enter IP manually"
            return self.async_show_form(
                step_id="discover",
                data_schema=vol.Schema(
                    {
                        vol.Required("host", default=default_ip): SelectSelector(
                            SelectSelectorConfig(
                                options=options,
                                custom_value=True,
                            )
                        ),
                    }
                ),
                errors=errors,
                description_placeholders={
                    "name": self._device_name,
                    "status": status,
                },
            )

        # No devices found at all — plain text input
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {vol.Required("host", default=default_ip): str}
            ),
            errors=errors,
            description_placeholders={
                "name": self._device_name,
                "status": "No Tuya devices found on network — enter IP manually",
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

    def _scan_network(self) -> dict[str, dict]:
        """Scan local network for Tuya devices.

        1. UDP broadcast scan (byID=True → keys are device IDs)
        2. TCP port 6668 scan to catch devices that don't broadcast
        Returns combined dict keyed by device_id where known, else by IP.
        """
        import concurrent.futures
        import socket as _socket

        _LOGGER.info("Scanning network for Tuya devices (looking for %s)...", self._device_id)
        result: dict[str, dict] = {}

        # Step 1: UDP broadcast
        try:
            udp_devices = tinytuya.deviceScan(verbose=False, maxretry=3, byID=True)
            _LOGGER.info("UDP scan found %d device(s): %s",
                         len(udp_devices),
                         {did: info.get("ip") for did, info in udp_devices.items()})
            result.update(udp_devices)
            if self._device_id in result:
                self._discovered_ip = result[self._device_id].get("ip")
        except Exception:
            _LOGGER.exception("UDP scan failed")

        # Step 2: TCP port 6668 scan for devices silent on UDP
        # Determine local subnet from known IPs
        known_ips = {info.get("ip") for info in result.values() if info.get("ip")}
        udp_ips = known_ips.copy()
        try:
            # Detect subnet from HA's own IP
            import socket
            local_ip = socket.gethostbyname(socket.gethostname())
            subnet_prefix = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet_prefix = "192.168.50"

        def tcp_check(i: int) -> str | None:
            ip = f"{subnet_prefix}.{i}"
            try:
                s = _socket.socket()
                s.settimeout(0.3)
                s.connect((ip, 6668))
                s.close()
                return ip
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
            tcp_found = [ip for ip in ex.map(tcp_check, range(1, 255)) if ip]

        _LOGGER.info("TCP port 6668 scan found %d device(s): %s", len(tcp_found), tcp_found)

        # Add TCP-found IPs not already in results (keyed by IP since no device_id)
        udp_result_ips = {info.get("ip") for info in result.values()}
        for ip in tcp_found:
            if ip not in udp_result_ips:
                result[ip] = {"ip": ip, "id": "", "version": "?", "origin": "tcp_scan"}

        if self._device_id not in result:
            _LOGGER.warning("Target %s not found by UDP; showing %d total candidates",
                            self._device_id, len(result))
        return result

    async def _create_tuya_local_entry(self, host: str) -> data_entry_flow.FlowResult:
        """Programmatically create a tuya_local config entry via its config flow.

        Returns abort result on failure (caller can retry with different IP)
        or create_entry on success.
        """
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

            # Step 3: Submit device details — triggers connection test
            _LOGGER.info(
                "Testing connection to %s at %s (key: %s...)",
                self._device_id, host, self._local_key[:4] if self._local_key else "?",
            )
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
            result_type = str(result.get("type", ""))
            step_id = result.get("step_id", "")
            _LOGGER.info(
                "tuya_local result: type=%s step=%s errors=%s",
                result_type, step_id, result.get("errors"),
            )

            # Connection test failed — device unreachable
            if step_id == "local":
                _LOGGER.warning(
                    "Connection failed for %s at %s", self._device_id, host,
                )
                return self.async_abort(reason="connection_failed")

            if result_type == "abort":
                reason = result.get("reason", "unknown")
                _LOGGER.warning("tuya_local flow aborted: %s", reason)
                return self.async_abort(reason=f"tuya_local_{reason}")

            # Step 4: Auto-select device type
            if step_id in ("select_type", "select_type_auto_detected"):
                device_type = self._pick_device_type(result, self._category)
                _LOGGER.info("Auto-selected device type: %s", device_type)
                result = await self.hass.config_entries.flow.async_configure(
                    flow_id, {"type": device_type}
                )
                step_id = result.get("step_id", "")
                result_type = str(result.get("type", ""))

            # Step 5: Set name
            if step_id == "choose_entities":
                result = await self.hass.config_entries.flow.async_configure(
                    flow_id, {"name": self._device_name}
                )
                result_type = str(result.get("type", ""))

            if result_type == "create_entry":
                _LOGGER.info(
                    "Created tuya_local entry for %s at %s", self._device_id, host,
                )
                ir.async_delete_issue(
                    self.hass, DOMAIN, f"new_device_{self._device_id}"
                )
                return self.async_create_entry(data={"result": "added_locally"})

            _LOGGER.warning(
                "Unexpected tuya_local flow: type=%s step=%s", result_type, step_id,
            )
            return self.async_abort(reason="unexpected_flow_result")

        except Exception:
            _LOGGER.exception("Failed to create tuya_local entry for %s", host)
            return self.async_abort(reason="creation_failed")

    def _pick_device_type(self, flow_result: dict, category: str) -> str:
        """Pick the best device type from tuya_local's available options.

        tuya_local uses SelectSelector with compound keys like
        'config_type||manufacturer||model'. We extract option values
        from the voluptuous schema's SelectSelector.
        """
        options: list[str] = []

        try:
            data_schema = flow_result.get("data_schema")
            if data_schema and hasattr(data_schema, "schema"):
                for key in data_schema.schema:
                    key_name = getattr(key, "schema", None) or str(key)
                    if key_name == "type":
                        selector = data_schema.schema[key]
                        # SelectSelector wraps config with options list
                        if hasattr(selector, "config"):
                            sel_options = selector.config.get("options", [])
                            for opt in sel_options:
                                if isinstance(opt, dict):
                                    options.append(opt.get("value", ""))
                                else:
                                    options.append(str(opt))
                        break
        except Exception:
            _LOGGER.debug("Failed to extract options from schema", exc_info=True)

        if not options:
            _LOGGER.warning("No device type options found in tuya_local flow")
            return ""

        _LOGGER.debug("Available device types: %s", options)

        # Try category hint — match against the config_type part (before ||)
        hint = CATEGORY_TYPE_HINTS.get(category, "")
        if hint:
            for opt in options:
                config_type = opt.split("||")[0] if "||" in opt else opt
                if hint in config_type:
                    return opt

        # Prefer energy monitoring variants
        for opt in options:
            config_type = opt.split("||")[0] if "||" in opt else opt
            if "energy" in config_type:
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
