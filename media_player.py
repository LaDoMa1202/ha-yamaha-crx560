"""
Yamaha CRX-N560 Media Player - v3.0

Fixes from capture.txt analysis:
  - Track skip: "Next" / "Prev" (confirmed working)
  - Tuner preset max: 30 (not 8)
  - Tuner state: uses new nested FM fields
  - Shuffle/Repeat: explicit set (not toggle)
  - Fast_Forward / Fast_Reverse mapped to STATE_PLAYING
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional
import asyncio

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
from homeassistant.components.media_player.const import MediaType, MediaClass, RepeatMode

try:
    from homeassistant.components.media_player.browse_media import BrowseMedia
except ImportError:
    from homeassistant.components.media_player import BrowseMedia

from homeassistant.const import STATE_OFF, STATE_IDLE, STATE_PLAYING, STATE_PAUSED
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .coordinator import YamahaCrxN560dCoordinator
from .const import (
    DOMAIN, VOLUME_MAX, MANUFACTURER, MODEL,
    AVAILABLE_SOURCES, SLEEP_VALUES, MAX_PRESETS,
    SOURCE_CD, SOURCE_TUNER, SOURCE_SERVER, SOURCE_NET_RADIO,
    SOURCE_USB, SOURCE_AIRPLAY, SOURCE_SPOTIFY,
    SOURCES_WITH_PLAYER,
)

_LOGGER = logging.getLogger(__name__)

# Display name → API name mapping
SOURCE_MAPPING = {
    "CD": "CD",
    "Tuner": "TUNER",
    "AUX1": "AUX1",
    "AUX2": "AUX2",
    "Digital 1": "DIGITAL1",
    "Digital 2": "DIGITAL2",
    "Server": "SERVER",
    "Net Radio": "NET RADIO",
    "USB": "USB",
    "AirPlay": "AirPlay",
    "Spotify": "Spotify",
}

REVERSE_SOURCE_MAPPING = {v: k for k, v in SOURCE_MAPPING.items()}

# Input sources that are analog-only (no playback controls)
ANALOG_SOURCES = {"AUX1", "AUX2", "DIGITAL1", "DIGITAL2"}

# Playback states from capture
PLAYBACK_STATE_MAP = {
    "Play": STATE_PLAYING,
    "Pause": STATE_PAUSED,
    "Stop": STATE_IDLE,
    "Fast_Forward": STATE_PLAYING,
    "Fast_Reverse": STATE_PLAYING,
}

SUPPORT_YAMAHA = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
)

SUPPORT_CD = SUPPORT_YAMAHA

SUPPORTED_PLAYBACK = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

SUPPORT_TUNER = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
)

SUPPORT_NET_RADIO = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)

SUPPORT_SERVER = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: YamahaCrxN560dCoordinator = entry.runtime_data
    async_add_entities([YamahaCrxN560dMP(coordinator, entry)])


class YamahaCrxN560dMP(CoordinatorEntity[YamahaCrxN560dCoordinator], MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = "receiver"
    _attr_source_list = list(SOURCE_MAPPING.keys())

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self._entry.title or MODEL,
            configuration_url=f"http://{self.coordinator.api.host}",
        )

    def _src(self) -> Optional[str]:
        """Return display source name for current input."""
        d = self.coordinator.data
        return REVERSE_SOURCE_MAPPING.get(d.input_sel, d.input_sel) if d else None

    @property
    def state(self) -> str:
        d = self.coordinator.data
        if d is None or d.power != "On":
            return STATE_OFF
        src = d.input_sel
        if src in ANALOG_SOURCES:
            return STATE_IDLE
        if src == "TUNER":
            return STATE_PLAYING if d.tuner_tuned else STATE_IDLE
        return PLAYBACK_STATE_MAP.get(d.playback_info, STATE_IDLE)

    @property
    def supported_features(self):
        src = self._src()
        if src == "Tuner":
            return SUPPORT_TUNER
        if src == "Net Radio":
            return SUPPORT_NET_RADIO
        if src == "Server":
            return SUPPORT_SERVER
        if src in ("CD", "USB", "AirPlay", "Spotify"):
            return SUPPORT_YAMAHA
        return SUPPORTED_PLAYBACK

    @property
    def volume_level(self):
        d = self.coordinator.data
        return (d.volume / VOLUME_MAX) if d else 0

    @property
    def is_volume_muted(self):
        d = self.coordinator.data
        return d.muted if d else False

    @property
    def source(self):
        return self._src()

    @property
    def media_position(self):
        d = self.coordinator.data
        return d.play_time if d else None

    @property
    def media_album_name(self):
        d = self.coordinator.data
        return d.album if d else None

    @property
    def media_artist(self):
        d = self.coordinator.data
        return d.artist if d else None

    @property
    def media_image_url(self):
        d = self.coordinator.data
        return d.album_art_url if d else None

    @property
    def media_track(self):
        d = self.coordinator.data
        return d.track_number if d else None

    @property
    def shuffle(self):
        d = self.coordinator.data
        return d.shuffle if d else False

    @property
    def media_position_updated_at(self):
        d = self.coordinator.data
        return dt_util.utcnow() if d and d.play_time is not None else None

    @property
    def media_title(self) -> Optional[str]:
        d = self.coordinator.data
        if d is None:
            return None
        if d.input_sel == "TUNER":
            # Build tuner title from new fields
            parts = []
            if d.tuner_program_service:
                parts.append(d.tuner_program_service.strip())
            if d.tuner_freq:
                parts.append(f"{d.tuner_freq / 100:.1f} MHz")
            if d.tuner_preset:
                parts.append(f"P{d.tuner_preset}")
            if d.tuner_radio_text_a:
                parts.append(d.tuner_radio_text_a.strip())
            return " | ".join(parts) if parts else "Tuner"
        if d.song:
            return d.song
        if d.artist:
            return d.artist
        return None

    @property
    def media_content_type(self):
        return MediaType.MUSIC

    @property
    def repeat(self) -> Optional[str]:
        d = self.coordinator.data
        if d is None:
            return None
        r = d.repeat
        if r == "All":
            return RepeatMode.ALL
        if r == "One":
            return RepeatMode.ONE
        return RepeatMode.OFF

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data
        attrs = {}
        if d:
            attrs["sleep_timer"] = d.sleep
            attrs["timer_mode"] = d.timer_mode
            if d.track_number is not None:
                attrs["track_number"] = d.track_number
            if d.total_tracks is not None:
                attrs["total_tracks"] = d.total_tracks
            # Tuner-specific
            if d.input_sel == "TUNER":
                if d.tuner_preset is not None:
                    attrs["tuner_preset"] = d.tuner_preset
                if d.tuner_freq is not None:
                    attrs["tuner_freq_mhz"] = d.tuner_freq / 100
                attrs["tuner_tuned"] = d.tuner_tuned
                if d.tuner_program_type:
                    attrs["tuner_program_type"] = d.tuner_program_type
        return attrs

    # ── Commands ─────────────────────────────────────────────────

    async def async_turn_on(self) -> None:
        await self.coordinator.api.set_power("On")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.api.set_power("Standby")
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        await self.coordinator.api.play_control("Play")
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        await self.coordinator.api.play_control("Pause")
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        await self.coordinator.api.play_control("Stop")
        await self.coordinator.async_request_refresh()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self.coordinator.api.toggle_shuffle(shuffle)
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: str) -> None:
        # Map HA RepeatMode to Yamaha values
        mode_map = {
            RepeatMode.OFF: "Off",
            RepeatMode.ALL: "All",
            RepeatMode.ONE: "One",
        }
        yamaha_mode = mode_map.get(repeat, "Off")
        await self.coordinator.api.toggle_repeat(yamaha_mode)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.api.set_volume(round(volume * VOLUME_MAX))
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.api.set_mute(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.api.set_input(SOURCE_MAPPING.get(source, source))
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        if self._src() == "Tuner":
            await self._next_preset()
        else:
            # FIXED: "Next" instead of "Skip Fwd" (confirmed in capture)
            await self.coordinator.api.play_control("Next")
            await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        if self._src() == "Tuner":
            await self._prev_preset()
        else:
            # FIXED: "Prev" instead of "Skip Rev" (confirmed in capture)
            await self.coordinator.api.play_control("Prev")
            await self.coordinator.async_request_refresh()

    async def async_play_media(self, media_type, media_id, **kwargs) -> None:
        src = self._src()
        if src == "Tuner" and media_type == "preset":
            await self.coordinator.api.set_tuner_preset(int(media_id))
        elif src == "Net Radio" and media_type == "station":
            await self._nav_play_station(media_id)
        elif src == "Server" and media_type == "music":
            await self._nav_play_track(media_id)
        elif src == "Server" and media_type == "info":
            return
        else:
            _LOGGER.warning("Unsupported: src=%s type=%s", src, media_type)
            return
        await self.coordinator.async_request_refresh()

    async def async_set_sleep_timer(self, value: str) -> None:
        if value not in SLEEP_VALUES:
            _LOGGER.warning("Invalid sleep: %s. Use: %s", value, SLEEP_VALUES)
            return
        await self.coordinator.api.set_sleep(value)
        await self.coordinator.async_request_refresh()

    async def async_toggle_tray(self) -> None:
        """Toggle CD tray open/close."""
        await self.coordinator.api.toggle_tray()

    async def _next_preset(self) -> None:
        """Cycle to next tuner preset (1-30)."""
        try:
            d = self.coordinator.data
            c = d.tuner_preset if d and d.tuner_preset else 1
            n = (c % MAX_PRESETS) + 1
            await self.coordinator.api.set_tuner_preset(n)
            await self.coordinator.async_request_refresh()
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Next preset error: %s", e)

    async def _prev_preset(self) -> None:
        """Cycle to previous tuner preset (1-30)."""
        try:
            d = self.coordinator.data
            c = d.tuner_preset if d and d.tuner_preset else 1
            p = ((c - 2) % MAX_PRESETS) + 1
            await self.coordinator.api.set_tuner_preset(p)
            await self.coordinator.async_request_refresh()
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Prev preset error: %s", e)

    # == Browse media =============================================

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        s = self._src()
        if s == "Net Radio":
            try:
                return await self._nr_root() if media_content_id is None else await self._nr_item(media_content_id)
            except Exception as e:
                _LOGGER.exception("NR error: %s", e)
                return None
        if s == "Server":
            try:
                return await self._srv_root() if media_content_id is None or media_content_id == "server_root" else await self._srv_item(media_content_id)
            except Exception as e:
                _LOGGER.exception("SRV error: %s", e)
                return None
        return None

    async def _nr_root(self):
        data = await self.coordinator.api.net_radio_get_list()
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            ch = []
            for node in tree[0][0]:
                if node.tag == "Current_List":
                    for line in node:
                        if line.tag.startswith("Line_"):
                            t = line.find("Txt")
                            a = line.find("Attribute")
                            if t is not None and a is not None and t.text and a.text == "Container":
                                ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=f"menu:{line.tag}", media_content_type="folder", title=t.text, can_play=False, can_expand=True))
            if not ch:
                ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id="empty", media_content_type="info", title="No stations", can_play=False, can_expand=False))
            return BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id="root", media_content_type="folder", title="NET RADIO", can_play=False, can_expand=True, children=ch)
        except ET.ParseError as e:
            _LOGGER.error("NR root XML: %s", e)
            return None

    async def _nr_item(self, mid):
        if not mid.startswith("menu:"):
            return None
        api = self.coordinator.api
        await api.net_radio_select(mid.split(":", 1)[1])
        data = await api.net_radio_get_list()
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            ch = []
            mn = "NET RADIO"
            for node in tree[0][0]:
                if node.tag == "Menu_Name":
                    mn = node.text
                elif node.tag == "Current_List":
                    for line in node:
                        if line.tag.startswith("Line_"):
                            t = line.find("Txt")
                            a = line.find("Attribute")
                            if t is not None and a is not None and t.text:
                                if a.text == "Container":
                                    ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=f"menu:{line.tag}", media_content_type="folder", title=t.text, can_play=False, can_expand=True))
                                elif a.text == "Item":
                                    ch.append(BrowseMedia(media_class=MediaClass.TRACK, media_content_id=f"station:{line.tag}", media_content_type="station", title=t.text, can_play=True, can_expand=False))
            return BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=mid, media_content_type="folder", title=mn, can_play=False, can_expand=True, children=ch)
        except ET.ParseError as e:
            _LOGGER.error("NR item XML: %s", e)
            return None

    async def _nav_play_station(self, mid):
        if not mid.startswith("station:"):
            return
        api = self.coordinator.api
        await api.net_radio_select(mid.split(":", 1)[1])
        await api.net_radio_play()

    async def _srv_root(self):
        api = self.coordinator.api
        await self._srv_reset()
        data = await api.server_get_list()
        if not data:
            return None
        p = self._srv_parse(data)
        if not p:
            return None
        ch = self._srv_ch(p["items"], "", p["menu_layer"])
        if not ch:
            ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id="empty", media_content_type="info", title="No servers", can_play=False, can_expand=False))
        return BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id="server_root", media_content_type="folder", title=p["menu_name"], can_play=False, can_expand=True, children=ch)

    async def _srv_item(self, mid):
        api = self.coordinator.api
        if mid.startswith("server_page_up:"):
            await api.server_page("Up")
            await asyncio.sleep(0.2)
            return await self._srv_cur(mid[15:])
        if mid.startswith("server_page_down:"):
            await api.server_page("Down")
            await asyncio.sleep(0.2)
            return await self._srv_cur(mid[17:])
        if not mid.startswith("server_menu:"):
            return await self._srv_back(mid)
        parts = mid.split(":")
        if len(parts) < 3:
            return None
        data = await self._srv_nav(parts[2:])
        if not data:
            return None
        p = self._srv_parse(data)
        if not p:
            return None
        bp = ":".join(parts[2:])
        ch = self._srv_ch(p["items"], bp, p["menu_layer"])
        self._srv_pg(ch, p["current_line"], p["max_line"], mid)
        self._srv_bn(ch, p["menu_layer"], parts)
        return BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=mid, media_content_type="folder", title=p["menu_name"], can_play=False, can_expand=True, children=ch)

    @staticmethod
    def _srv_parse(data):
        try:
            tree = ET.fromstring(data)
            info = {"menu_name": "Server", "menu_layer": 1, "current_line": 1, "max_line": 1, "items": []}
            for node in tree[0][0]:
                if node.tag == "Menu_Name":
                    info["menu_name"] = node.text or "Server"
                elif node.tag == "Menu_Layer":
                    info["menu_layer"] = int(node.text) if node.text else 1
                elif node.tag == "Cursor_Position":
                    cl = node.find("Current_Line")
                    ml = node.find("Max_Line")
                    if cl is not None:
                        info["current_line"] = int(cl.text) if cl.text else 1
                    if ml is not None:
                        info["max_line"] = int(ml.text) if ml.text else 1
                elif node.tag == "Current_List":
                    for line in node:
                        if line.tag.startswith("Line_"):
                            t = line.find("Txt")
                            a = line.find("Attribute")
                            if t is not None and a is not None and t.text:
                                info["items"].append({"line_id": line.tag, "title": t.text, "attribute": a.text})
            return info
        except ET.ParseError as e:
            _LOGGER.error("SRV parse: %s", e)
            return None

    @staticmethod
    def _srv_ch(items, base="", layer=1):
        ch = []
        for i in items:
            np = f"{base}:{i['line_id']}" if base else i["line_id"]
            if i["attribute"] == "Container":
                cls = MediaClass.ALBUM if layer > 4 else MediaClass.DIRECTORY
                ch.append(BrowseMedia(title=i["title"], media_class=cls, media_content_id=f"server_menu:root:{np}", media_content_type="folder", can_play=False, can_expand=True))
            elif i["attribute"] == "Item":
                ch.append(BrowseMedia(title=i["title"], media_class=MediaClass.TRACK, media_content_id=f"server_track:root:{np}", media_content_type="music", can_play=True, can_expand=False))
        return ch

    @staticmethod
    def _srv_pg(ch, cl, ml, bid):
        if ml <= 8:
            return
        if cl > 1:
            ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=f"server_page_up:{bid}", media_content_type="info", title="Prev Page", can_play=False, can_expand=True))
        if cl + 7 < ml:
            ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=f"server_page_down:{bid}", media_content_type="info", title="Next Page", can_play=False, can_expand=True))
        ch.append(BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id="page_info", media_content_type="info", title=f"Page {(cl-1)//8+1}/{(ml-1)//8+1} ({ml})", can_play=False, can_expand=False))

    @staticmethod
    def _srv_bn(ch, layer, parts):
        if layer > 1:
            pp = ":".join(parts[2:-1] if len(parts) > 3 else [])
            bid = f"server_menu:root:{pp}" if pp else "server_root"
            ch.insert(0, BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=bid, media_content_type="folder", title="Back", can_play=False, can_expand=True))

    async def _srv_nav(self, path):
        api = self.coordinator.api
        await self._srv_reset()
        for step in path:
            await api.server_select(step)
            await asyncio.sleep(0.5)
        for _ in range(5):
            data = await api.server_get_list()
            if data and "Menu_Status>Busy<" not in data:
                return data
            await asyncio.sleep(0.5)
        return None

    async def _nav_play_track(self, mid):
        if not mid.startswith("server_track:"):
            return
        lid = None
        for part in reversed(mid.split(":")):
            if part.startswith("Line_"):
                lid = part
                break
        if not lid:
            return
        api = self.coordinator.api
        await api.server_select(lid)
        await asyncio.sleep(0.2)
        await api.server_play()

    async def _srv_back(self, mid):
        if not mid.startswith("server_back:"):
            return None
        api = self.coordinator.api
        await api.server_return()
        data = await api.server_get_list()
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            ml = 1
            for n in tree[0][0]:
                if n.tag == "Menu_Layer":
                    ml = int(n.text) if n.text else 1
                    break
            return await self._srv_root() if ml == 1 else await self._srv_item("server_menu:current")
        except ET.ParseError as e:
            _LOGGER.error("SRV back: %s", e)
            return None

    async def _srv_cur(self, mid):
        api = self.coordinator.api
        parts = mid.split(":")
        data = None
        for _ in range(5):
            data = await api.server_get_list()
            if data and "Menu_Status>Busy<" not in data:
                break
            await asyncio.sleep(0.5)
        if not data:
            return None
        cp = ":".join(parts[2:]) if len(parts) > 2 else ""
        p = self._srv_parse(data)
        if not p:
            return None
        ch = self._srv_ch(p["items"], cp, p["menu_layer"])
        self._srv_pg(ch, p["current_line"], p["max_line"], mid)
        self._srv_bn(ch, p["menu_layer"], parts)
        return BrowseMedia(media_class=MediaClass.DIRECTORY, media_content_id=mid, media_content_type="folder", title=p["menu_name"], can_play=False, can_expand=True, children=ch)

    async def _srv_reset(self):
        api = self.coordinator.api
        data = await api.server_get_list()
        if not data:
            return
        try:
            tree = ET.fromstring(data)
            ml = 1
            for n in tree[0][0]:
                if n.tag == "Menu_Layer":
                    ml = int(n.text) if n.text else 1
                    break
            while ml > 1:
                await api.server_return()
                data = await api.server_get_list()
                if not data:
                    break
                tree = ET.fromstring(data)
                ml = 1
                for n in tree[0][0]:
                    if n.tag == "Menu_Layer":
                        ml = int(n.text) if n.text else 1
                        break
        except ET.ParseError:
            pass

