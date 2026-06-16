"""Async API client for Yamaha CRX-N560 XML protocol.

v3.0 – Fixes based on capture.txt analysis of NP_CONTROLLER/4.50 (iOS):
  - Track skip: caller uses play_control("Next") / play_control("Prev")
  - Tray: uses "Open/Close" instead of "Toggle"
  - Tuner preset: nested inside <FM><Preset_Sel>X</Preset_Sel></FM>
  - Tuner Play_Info: response nested in <Band>FM</Band><FM>...</FM>
  - New: Alarm Timer get/set
  - New: Fast_Forward_Start/End, Fast_Reverse_Start/End via play_control()
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional

import aiohttp

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

XML_HEADER = '<?xml version="1.0" encoding="utf-8"?>'


class YamahaCrxN560dApi:

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host
        self._base_url = f"http://{host}/YamahaRemoteControl/ctrl"

    @property
    def host(self) -> str:
        return self._host

    # ── Low-level transport ──────────────────────────────────────

    async def _do_request(self, xml_data: str) -> str:
        payload = XML_HEADER + xml_data
        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with self._session.post(self._base_url, data=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    _LOGGER.warning("API error %d: %s", resp.status, xml_data)
                return await resp.text()
        except aiohttp.ClientError as exc:
            _LOGGER.error("Request failed: %s", exc)
            return ""
        except Exception as exc:
            _LOGGER.error("Unexpected error: %s", exc)
            return ""

    async def do_get(self, body: str) -> str:
        return await self._do_request(f'<YAMAHA_AV cmd="GET">{body}</YAMAHA_AV>')

    async def do_put(self, body: str) -> str:
        return await self._do_request(f'<YAMAHA_AV cmd="PUT">{body}</YAMAHA_AV>')

    # ── System: Basic Status ─────────────────────────────────────

    async def get_basic_status(self) -> Optional[dict]:
        data = await self.do_get("<System><Basic_Status>GetParam</Basic_Status></System>")
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            result = {}
            for node in tree[0][0]:
                if node.tag == "Power_Control":
                    pwr = node.find("Power")
                    slp = node.find("Sleep")
                    result["power"] = pwr.text if pwr is not None and pwr.text else "Standby"
                    result["sleep"] = slp.text if slp is not None and slp.text else "Off"
                elif node.tag == "Volume":
                    lvl = node.find("Lvl")
                    mute = node.find("Mute")
                    result["volume"] = int(lvl.text) if lvl is not None and lvl.text else 0
                    result["muted"] = mute.text == "On" if mute is not None else False
                elif node.tag == "Input":
                    sel = node.find("Input_Sel")
                    result["input_sel"] = sel.text if sel is not None else "CD"
            return result
        except (ET.ParseError, Exception) as exc:
            _LOGGER.error("Failed to parse basic status: %s", exc)
            return None

    # ── Player: Play Info (CD / USB / Server / Net Radio) ────────

    async def get_play_info(self) -> Optional[dict]:
        data = await self.do_get("<Player><Play_Info>GetParam</Play_Info></Player>")
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            result = {"playback_info": "Stop", "shuffle": False, "repeat": "Off",
                      "play_time": None, "track_number": None, "total_tracks": None,
                      "artist": None, "album": None, "song": None, "album_art_url": None}
            for node in tree[0][0]:
                if node.tag == "Playback_Info":
                    result["playback_info"] = node.text or "Stop"
                elif node.tag == "Play_Mode":
                    sh = node.find("Shuffle")
                    rp = node.find("Repeat")
                    if sh is not None:
                        result["shuffle"] = sh.text == "On"
                    if rp is not None:
                        result["repeat"] = rp.text or "Off"
                elif node.tag == "Play_Time":
                    result["play_time"] = int(node.text) if node.text else None
                elif node.tag == "Track_Number":
                    val = int(node.text) if node.text else 0
                    result["track_number"] = val if val > 0 else None
                elif node.tag == "Total_Tracks":
                    val = int(node.text) if node.text else 0
                    result["total_tracks"] = val if val > 0 else None
                elif node.tag == "Meta_Info":
                    a = node.find("Artist")
                    b = node.find("Album")
                    s = node.find("Song")
                    result["artist"] = a.text if a is not None and a.text else None
                    result["album"] = b.text if b is not None and b.text else None
                    result["song"] = s.text if s is not None and s.text else None
                elif node.tag == "Album_ART":
                    u = node.find("URL")
                    if u is not None and u.text:
                        result["album_art_url"] = f"http://{self._host}{u.text}"
            return result
        except (ET.ParseError, Exception) as exc:
            _LOGGER.error("Failed to parse play info: %s", exc)
            return None

    # ── Tuner: Play Info (FIXED for nested FM structure) ─────────
    #
    # Capture shows the response structure:
    #   <Tuner><Play_Info>
    #     <Feature_Availability>Ready</Feature_Availability>
    #     <Band>FM</Band>
    #     <FM>
    #       <Preset><Preset_Sel>10</Preset_Sel></Preset>
    #       <Tuning><Freq>9215</Freq></Tuning>
    #       <Signal_Info><Tuned>Negate|Assert</Tuned></Signal_Info>
    #       <Meta_Info>
    #         <Program_Type>...</Program_Type>
    #         <Program_Service>...</Program_Service>
    #         <Radio_Text_A>...</Radio_Text_A>
    #         <Radio_Text_B>...</Radio_Text_B>
    #       </Meta_Info>
    #     </FM>
    #   </Play_Info></Tuner>

    async def get_tuner_play_info(self) -> Optional[dict]:
        data = await self.do_get("<Tuner><Play_Info>GetParam</Play_Info></Tuner>")
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            result = {
                "band": "FM",
                "tuner_preset": None,
                "tuner_freq": None,
                "tuner_tuned": False,
                "tuner_program_type": None,
                "tuner_program_service": None,
                "tuner_radio_text_a": None,
                "tuner_radio_text_b": None,
            }
            play_info = tree.find(".//Play_Info")
            if play_info is None:
                return result

            band_node = play_info.find("Band")
            if band_node is not None and band_node.text:
                result["band"] = band_node.text

            # Parse FM sub-tree (nested structure from capture)
            fm = play_info.find("FM")
            if fm is not None:
                # Preset
                preset_sel = fm.find("Preset/Preset_Sel")
                if preset_sel is not None and preset_sel.text:
                    try:
                        result["tuner_preset"] = int(preset_sel.text)
                    except ValueError:
                        pass

                # Frequency
                freq = fm.find("Tuning/Freq")
                if freq is not None and freq.text:
                    try:
                        result["tuner_freq"] = int(freq.text)
                    except ValueError:
                        pass

                # Signal tuned?
                tuned = fm.find("Signal_Info/Tuned")
                if tuned is not None and tuned.text:
                    result["tuner_tuned"] = tuned.text == "Assert"

                # RDS Meta Info
                meta = fm.find("Meta_Info")
                if meta is not None:
                    pt = meta.find("Program_Type")
                    ps = meta.find("Program_Service")
                    rta = meta.find("Radio_Text_A")
                    rtb = meta.find("Radio_Text_B")
                    result["tuner_program_type"] = pt.text if pt is not None and pt.text else None
                    result["tuner_program_service"] = ps.text if ps is not None and ps.text else None
                    result["tuner_radio_text_a"] = rta.text if rta is not None and rta.text else None
                    result["tuner_radio_text_b"] = rtb.text if rtb is not None and rtb.text else None

            return result
        except (ET.ParseError, Exception) as exc:
            _LOGGER.error("Failed to parse tuner play info: %s", exc)
            return None

    # ── System: Device Config ────────────────────────────────────

    async def get_device_config(self) -> Optional[dict]:
        data = await self.do_get("<System><Config>GetParam</Config></System>")
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            result = {}
            cfg = tree.find(".//Config")
            if cfg is not None:
                mn = cfg.find("Model_Name")
                sid = cfg.find("System_ID")
                ver = cfg.find("Version")
                fe = cfg.find("Feature_Existence")
                result["model_name"] = mn.text if mn is not None else None
                result["system_id"] = sid.text if sid is not None else None
                result["version"] = ver.text if ver is not None else None
                result["features"] = fe.text if fe is not None else None
                rng = cfg.find("Range_and_Step/Volume")
                if rng is not None:
                    vmin = rng.find("Min")
                    vmax = rng.find("Max")
                    result["volume_min"] = int(vmin.text) if vmin is not None and vmin.text else 0
                    result["volume_max"] = int(vmax.text) if vmax is not None and vmax.text else 60
            return result
        except (ET.ParseError, Exception) as exc:
            _LOGGER.error("Failed to parse device config: %s", exc)
            return None

    # ── System: Commands ─────────────────────────────────────────

    async def set_power(self, state: str) -> None:
        """Set power On or Standby."""
        await self.do_put(f"<System><Power_Control><Power>{state}</Power></Power_Control></System>")

    async def set_volume(self, level: int) -> None:
        await self.do_put(f"<System><Volume><Lvl>{level}</Lvl></Volume></System>")

    async def set_mute(self, mute: bool) -> None:
        val = "On" if mute else "Off"
        await self.do_put(f"<System><Volume><Mute>{val}</Mute></Volume></System>")

    async def set_input(self, source: str) -> None:
        await self.do_put(f"<System><Input><Input_Sel>{source}</Input_Sel></Input></System>")

    async def set_sleep(self, value: str) -> None:
        """Set sleep timer. Values: Off, 30 min, 60 min, 90 min, 120 min."""
        await self.do_put(f"<System><Power_Control><Sleep>{value}</Sleep></Power_Control></System>")

    # ── Player: Playback Control ─────────────────────────────────
    #
    # Valid commands from capture:
    #   Play, Stop, Pause, Next, Prev,
    #   Fast_Forward_Start, Fast_Forward_End,
    #   Fast_Reverse_Start, Fast_Reverse_End

    async def play_control(self, command: str) -> None:
        await self.do_put(
            f"<Player><Play_Control><Playback>{command}</Playback></Play_Control></Player>"
        )

    # ── Player: Shuffle / Repeat ─────────────────────────────────

    async def toggle_shuffle(self, on: bool) -> None:
        val = "On" if on else "Off"
        await self.do_put(
            f"<Player><Play_Control><Play_Mode><Shuffle>{val}</Shuffle></Play_Mode></Play_Control></Player>"
        )

    async def toggle_repeat(self, mode: str) -> None:
        """Set repeat mode: Off, One, All."""
        await self.do_put(
            f"<Player><Play_Control><Play_Mode><Repeat>{mode}</Repeat></Play_Mode></Play_Control></Player>"
        )

    # ── Tuner: Preset Control (FIXED – nested in <FM>) ──────────
    #
    # Capture shows the correct format:
    #   <Tuner><Play_Control><Preset><FM>
    #     <Preset_Sel>10</Preset_Sel>
    #   </FM></Preset></Play_Control></Tuner>

    async def set_tuner_preset(self, preset: int) -> None:
        await self.do_put(
            f"<Tuner><Play_Control><Preset><FM>"
            f"<Preset_Sel>{preset}</Preset_Sel>"
            f"</FM></Preset></Play_Control></Tuner>"
        )

    # ── CD Tray (FIXED – uses "Open/Close") ──────────────────────
    #
    # Capture: <System><Misc><Tray>Open/Close</Tray></Misc></System> → RC="0"

    async def toggle_tray(self) -> None:
        await self.do_put("<System><Misc><Tray>Open/Close</Tray></Misc></System>")

    # ── Alarm Timer (NEW from capture) ───────────────────────────
    #
    # Capture shows:
    #   GET <System><Misc><Timer><Mode>GetParam</Mode></Timer></Misc></System>
    #   → <Mode>Off</Mode>  or  <Mode>On</Mode>
    #
    #   GET <System><Misc><Timer><Param>GetParam</Param></Timer></Misc></System>
    #   → <Param>
    #       <Start_Time>07:00</Start_Time>
    #       <Volume>20</Volume>
    #       <Repeat>Once|Every</Repeat>
    #     </Param>
    #
    #   PUT <System><Misc><Timer><Mode>On</Mode></Timer></Misc></System>
    #   PUT <System><Misc><Timer><Param>
    #       <Start_Time>07:30</Start_Time><Volume>25</Volume><Repeat>Every</Repeat>
    #     </Param></Timer></Misc></System>

    async def get_timer_mode(self) -> Optional[str]:
        data = await self.do_get(
            "<System><Misc><Timer><Mode>GetParam</Mode></Timer></Misc></System>"
        )
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            mode = tree.find(".//Mode")
            return mode.text if mode is not None and mode.text else "Off"
        except (ET.ParseError, Exception):
            return None

    async def get_timer_param(self) -> Optional[dict]:
        data = await self.do_get(
            "<System><Misc><Timer><Param>GetParam</Param></Timer></Misc></System>"
        )
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            result = {}
            param = tree.find(".//Param")
            if param is not None:
                st = param.find("Start_Time")
                vol = param.find("Volume")
                rep = param.find("Repeat")
                result["start_time"] = st.text if st is not None and st.text else None
                result["volume"] = int(vol.text) if vol is not None and vol.text else None
                result["repeat"] = rep.text if rep is not None and rep.text else "Once"
            return result
        except (ET.ParseError, Exception):
            return None

    async def set_timer_mode(self, mode: str) -> None:
        """Set timer mode: On or Off."""
        await self.do_put(
            f"<System><Misc><Timer><Mode>{mode}</Mode></Timer></Misc></System>"
        )

    async def set_timer_param(self, start_time: str, volume: int, repeat: str = "Once") -> None:
        """Set timer parameters."""
        await self.do_put(
            f"<System><Misc><Timer><Param>"
            f"<Start_Time>{start_time}</Start_Time>"
            f"<Volume>{volume}</Volume>"
            f"<Repeat>{repeat}</Repeat>"
            f"</Param></Timer></Misc></System>"
        )

    # ── Server / Net Radio: List Navigation ──────────────────────

    async def server_get_list_info(self) -> Optional[dict]:
        data = await self.do_get("<Player><List_Info>GetParam</List_Info></Player>")
        if not data:
            return None
        try:
            tree = ET.fromstring(data)
            li = tree.find(".//List_Info")
            if li is None:
                return None
            result = {
                "menu_status": "Ready",
                "menu_layer": 1,
                "menu_name": "",
                "lines": [],
                "current_line": 1,
                "max_line": 0,
            }
            ms = li.find("Menu_Status")
            if ms is not None and ms.text:
                result["menu_status"] = ms.text
            ml = li.find("Menu_Layer")
            if ml is not None and ml.text:
                result["menu_layer"] = int(ml.text)
            mn = li.find("Menu_Name")
            if mn is not None and mn.text:
                result["menu_name"] = mn.text
            cl = li.find("Current_List")
            if cl is not None:
                for i in range(1, 9):
                    line = cl.find(f"Line_{i}")
                    if line is not None:
                        txt = line.find("Txt")
                        attr = line.find("Attribute")
                        result["lines"].append({
                            "index": i,
                            "text": txt.text if txt is not None and txt.text else "",
                            "attribute": attr.text if attr is not None and attr.text else "Unselectable",
                        })
            cp = li.find("Cursor_Position")
            if cp is not None:
                cur = cp.find("Current_Line")
                mx = cp.find("Max_Line")
                result["current_line"] = int(cur.text) if cur is not None and cur.text else 1
                result["max_line"] = int(mx.text) if mx is not None and mx.text else 0
            return result
        except (ET.ParseError, Exception) as exc:
            _LOGGER.error("Failed to parse list info: %s", exc)
            return None

    async def server_select_line(self, line: int) -> None:
        await self.do_put(
            f"<Player><List_Control><Direct_Sel>Line_{line}</Direct_Sel></List_Control></Player>"
        )

    async def server_cursor(self, direction: str) -> None:
        """Send cursor command: Up, Down, Sel, Return."""
        await self.do_put(
            f"<Player><List_Control><Cursor>{direction}</Cursor></List_Control></Player>"
        )

    async def server_page(self, direction: str) -> None:
        """Send page command: Up or Down."""
        await self.do_put(
            f"<Player><List_Control><Page>{direction}</Page></List_Control></Player>"
        )

    async def net_radio_select_line(self, line: int) -> None:
        await self.server_select_line(line)

    async def net_radio_cursor(self, direction: str) -> None:
        await self.server_cursor(direction)


    # ── Net Radio: Legacy list methods (used by browse_media) ────

    async def net_radio_get_list(self) -> str:
        return await self.do_get("<NET_RADIO><List_Info>GetParam</List_Info></NET_RADIO>")

    async def net_radio_select(self, line_id: str) -> None:
        await self.do_put(f"<NET_RADIO><List_Control><Direct_Sel>{line_id}</Direct_Sel></List_Control></NET_RADIO>")

    async def net_radio_play(self) -> None:
        await self.do_put("<NET_RADIO><Play_Control><Playback>Play</Playback></Play_Control></NET_RADIO>")

    # ── Server: Legacy list methods (used by browse_media) ───────

    async def server_get_list(self) -> str:
        return await self.do_get("<SERVER><List_Info>GetParam</List_Info></SERVER>")

    async def server_select(self, line_id: str) -> None:
        await self.do_put(f"<SERVER><List_Control><Direct_Sel>{line_id}</Direct_Sel></List_Control></SERVER>")

    async def server_page(self, direction: str) -> None:
        await self.do_put(f"<SERVER><List_Control><Page>{direction}</Page></List_Control></SERVER>")

    async def server_return(self) -> None:
        await self.do_put("<SERVER><List_Control><Cursor>Return</Cursor></List_Control></SERVER>")

    async def server_play(self) -> None:
        await self.do_put("<SERVER><Play_Control><Playback>Play</Playback></Play_Control></SERVER>")
