# Tuya Bridge for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Monitors your Tuya Cloud account for devices that are not yet managed locally by [Tuya Local](https://github.com/make-all/tuya-local). When new devices are found, Tuya Bridge creates a notification in Home Assistant **Repairs** so you can add them locally with one click, including automatic network discovery.

## Features

- **Auto-detect new Tuya Cloud devices** -- scans your cloud account on a schedule
- **Network discovery** -- finds device IP and local key via tinytuya UDP scan
- **One-click local device setup** -- adds the device to Tuya Local directly from the repair notification
- **Cloud Entity support** -- for devices that cannot work locally (coming soon)

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three-dot menu (top right) and select **Custom repositories**
3. Add repository URL: `https://github.com/consolover5-collab/tuya-bridge`
4. Category: **Integration**
5. Click **Add**, then find "Tuya Bridge" in the HACS store and install it
6. Restart Home Assistant

### Manual

Copy the `custom_components/tuya_bridge` directory into your Home Assistant `/config/custom_components/` folder, then restart Home Assistant.

## Configuration

1. Go to **Settings** > **Integrations** > **Add Integration**
2. Search for **Tuya Bridge**
3. Enter your Tuya IoT Platform credentials (from [developer.tuya.com](https://developer.tuya.com)):
   - **Access ID** -- your Cloud project Access ID / Client ID
   - **Access Secret** -- your Cloud project Access Secret / Client Secret
   - **Region** -- the data center region for your account (e.g. Central Europe, Western America, etc.)
   - **Any Device ID** -- the ID of any device in your Tuya account (used for API validation)

## How it works

1. **Scans Tuya Cloud every 30 minutes** to fetch the list of all devices in your account
2. **Compares with existing Tuya Local entries** to find devices that are not yet managed locally
3. **Creates a repair notification** for each unmanaged device
4. **Click the repair** to choose an action:
   - **Add Locally** -- runs a network scan to find the device on your LAN and sets it up through Tuya Local
   - **Create Cloud Entity** -- creates a Home Assistant entity backed by Tuya Cloud API (coming soon)

## Requirements

- **Home Assistant** 2024.1 or newer
- **[Tuya Local](https://github.com/make-all/tuya-local)** integration installed
- **Tuya IoT Platform** account at [developer.tuya.com](https://developer.tuya.com) with a Cloud project that has the IoT Core API enabled

## Roadmap

- Cloud Entity creation for battery-powered and other cloud-only devices
- Device type auto-selection improvements during local setup
