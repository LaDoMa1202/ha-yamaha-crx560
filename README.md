# 🎛️ Yamaha CRX-N560 – Home Assistant Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/lars-dobelmann/yamaha-crx-n560-ha?include_prereleases&style=flat-square)](https://github.com/lars-dobelmann/yamaha-crx-n560-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![HA version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue?style=flat-square)](https://www.home-assistant.io/)

A fully‑featured **Home Assistant** custom integration for the **Yamaha CRX‑N560** (and similar legacy Yamaha receivers that use the **HTTP/XML** remote‑control API — *not* MusicCast / YNCA).

> **Note:** This integration was developed by reverse‑engineering the Yamaha NP Controller iOS app protocol via packet capture and verified against a real CRX‑N560 unit (firmware 1.17/1.01).

---

## ✨ Features

### Media Player Entity

| Feature | Details |
|---|---|
| 🔌 **Power** | On / Standby |
| 🔊 **Volume** | Set level (0–60), Mute toggle |
| 📡 **Source Select** | CD · Tuner · AUX 1 · AUX 2 · Digital 1 · Digital 2 · Server · Net Radio · USB · AirPlay · Spotify |
| ▶️ **Playback** | Play · Pause · Stop |
| ⏭️ **Track Skip** | Next / Previous (true track skip — not fast‑forward!) |
| 🔀 **Shuffle** | On / Off |
| 🔁 **Repeat** | Off / One / All |
| 📻 **Tuner Presets** | 30 FM presets — cycle via Next/Prev or jump to any preset |
| 📡 **Tuner RDS** | Program Service name, Radio Text, frequency display |
| 🎵 **Media Info** | Artist, Album, Song, Track Number, Play Time, Album Art |
| 📂 **Browse Media** | Full tree navigation for Server (DLNA/UPnP) and Net Radio |
| ⏩ **Fast Forward/Rewind** | API support for seek within track |

### Additional Entities

| Entity | Type | Description |
|---|---|---|
| 💤 **Sleep Timer** | `select` | Set sleep timer: Off / 30 / 60 / 90 / 120 min |
| 💿 **CD Tray** | `button` | One‑press open/close toggle for the CD tray |

### State Attributes

- `sleep_timer` – Current sleep timer setting
- `timer_mode` – Alarm timer On/Off
- `track_number` / `total_tracks` – Current track info
- `tuner_preset` – Active FM preset number (when on Tuner)
- `tuner_freq_mhz` – Tuned frequency in MHz
- `tuner_tuned` – Whether signal is locked
- `tuner_program_type` – RDS program type

---

## 📦 Installation

### Option A: HACS (recommended)

1. Open **HACS** → **Integrations** → ⋮ Menu → **Custom repositories**
2. Add repository URL: `https://github.com/lars-dobelmann/yamaha-crx-n560-ha`
3. Category: **Integration**
4. Click **Download** and restart Home Assistant

### Option B: Manual

1. Download the [latest release](https://github.com/lars-dobelmann/yamaha-crx-n560-ha/releases)
2. Copy the `custom_components/yamaha_crx_n560d/` folder to your HA config directory
3. Restart Home Assistant

### Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Yamaha CRX‑N560**
3. Enter the IP address of your receiver
4. Done!

---

## 📁 File Structure

```
custom_components/yamaha_crx_n560d/
├── __init__.py            # Integration setup, platform registration
├── api.py                 # YamahaCrxN560dApi – all XML commands
├── button.py              # CD Tray button entity
├── config_flow.py         # UI-based configuration flow
├── const.py               # Constants (sources, volume range, etc.)
├── coordinator.py         # DataUpdateCoordinator (polling)
├── manifest.json          # Integration manifest (v3.0.0)
├── media_player.py        # Main MediaPlayerEntity + Browse Media
├── models.py              # YamahaState dataclass
├── select.py              # Sleep Timer select entity
├── strings.json           # UI strings
└── translations/
    └── en.json            # English translations
```

---

## 🔧 Technical Details

### API Protocol

| Property | Value |
|---|---|
| **Transport** | HTTP POST |
| **Content‑Type** | `text/xml; charset=UTF-8` |
| **Endpoint** | `http://<IP>/YamahaRemoteControl/ctrl` |
| **Request format** | `<YAMAHA_AV cmd="GET\|PUT">...</YAMAHA_AV>` |
| **Success response** | `RC="0"` |
| **Error responses** | `RC="2"` (not supported), `RC="3"` (invalid), `RC="4"` (busy) |

### Confirmed Hardware

| Property | Value |
|---|---|
| **Model** | Yamaha CRX-N560 |
| **Description** | Network CD Receiver |
| **Firmware** | 1.17 / 1.01 |
| **Server header** | `AV_Receiver/3.1 (CRX-N560)` |
| **Features** | CD, Tuner, AUX1, AUX2, Digital1, Digital2, Server, Net Radio, USB, AirPlay, Spotify |
| **Volume range** | 0–60 (step 1) |
| **FM range** | 87.50 – 108.00 MHz (step 0.05) |
| **FM Presets** | 30 |

---

## ⚠️ Known Limitations

| Limitation | Details |
|---|---|
| **Equalizer** | Most EQ commands return `RC="2"` (not supported by hardware) |
| **Speaker Grouping** | Not supported by this hardware |
| **Repeat One + Shuffle** | Cannot be active simultaneously (hardware limitation) |
| **Position Seek** | API supports fast‑forward/rewind but not "jump to position X" |
| **Album Art (CD)** | CD tracks do not provide metadata or album art |

---

## 🔄 Compatibility

This integration may also work with other Yamaha receivers using the same legacy XML API:

- Yamaha CRX-N560 / CRX-N560D
- Yamaha MCR-N560 (micro component system using CRX-N560)
- Other Yamaha receivers with `X_YamahaRemoteControl:1` service

> If you've tested with a different model, please open an issue or PR!

---

## 📋 Changelog

### v3.0.0 (2026-06-16)
- 🔴 **Fix:** Track skip now uses `Next`/`Prev` (confirmed via capture analysis)
- 🔴 **Fix:** CD tray uses correct `Open/Close` command
- 🔴 **Fix:** Tuner preset XML corrected (nested `<FM>` structure)
- 🔴 **Fix:** Tuner Play_Info parser rewritten for nested FM response
- 🔴 **Fix:** Tuner presets expanded from 8 to 30
- 🆕 **New:** Sleep Timer as `select` entity (visible in HA UI)
- 🆕 **New:** CD Tray as `button` entity (visible in HA UI)
- 🆕 **New:** Alarm Timer API support
- 🆕 **New:** Tuner RDS data display (Program Service, Radio Text)
- 🆕 **New:** `Fast_Forward` / `Fast_Reverse` playback states
- ✅ Shuffle/Repeat: explicit set instead of toggle

### v2.2
- Initial working version with Server/Net Radio browse media

---

## 📖 References

- [Yamaha XML API Documentation (Community)](https://www.heimkino-praxis.de/yamaha-netzwerk-steuerung/)
- [rxv Python Library](https://github.com/wuub/rxv)
- [HA Media Player Developer Docs](https://developers.home-assistant.io/docs/core/entity/media-player)
- [HACS Documentation](https://hacs.xyz/)

---

## 📄 License

MIT License – see [LICENSE](LICENSE) for details.

---
