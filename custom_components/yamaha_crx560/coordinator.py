"""DataUpdateCoordinator for Yamaha CRX-N560.

v3.0 – Fixes based on capture.txt analysis:
  - Tuner fields now use correct nested FM structure
  - Added timer_mode polling
"""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YamahaCrxN560dApi
from .const import DOMAIN
from .models import YamahaState

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = 10

PLAYABLE_SOURCES = {"Spotify", "NET RADIO", "SERVER", "USB", "AirPlay", "CD"}


class YamahaCrxN560dCoordinator(DataUpdateCoordinator[YamahaState]):

    def __init__(self, hass: HomeAssistant, api: YamahaCrxN560dApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=SCAN_INTERVAL))
        self.api = api
        self.device_config: dict = {}

    async def _async_update_data(self) -> YamahaState:
        status = await self.api.get_basic_status()
        if status is None:
            raise UpdateFailed("Failed to get basic status")

        state = YamahaState(
            power=status.get("power", "Standby"),
            volume=status.get("volume", 0),
            muted=status.get("muted", False),
            input_sel=status.get("input_sel", "CD"),
            sleep=status.get("sleep", "Off"),
        )

        if state.power == "On":
            if state.input_sel == "TUNER":
                tuner = await self.api.get_tuner_play_info()
                if tuner:
                    state.band = tuner.get("band", "FM")
                    state.tuner_preset = tuner.get("tuner_preset")
                    state.tuner_freq = tuner.get("tuner_freq")
                    state.tuner_tuned = tuner.get("tuner_tuned", False)
                    state.tuner_program_type = tuner.get("tuner_program_type")
                    state.tuner_program_service = tuner.get("tuner_program_service")
                    state.tuner_radio_text_a = tuner.get("tuner_radio_text_a")
                    state.tuner_radio_text_b = tuner.get("tuner_radio_text_b")
                    # Tuner is "playing" when signal is tuned
                    state.playback_info = "Play" if state.tuner_tuned else "Stop"

            elif state.input_sel in PLAYABLE_SOURCES:
                play = await self.api.get_play_info()
                if play:
                    state.playback_info = play.get("playback_info", "Stop")
                    state.shuffle = play.get("shuffle", False)
                    state.repeat = play.get("repeat", "Off")
                    state.play_time = play.get("play_time")
                    state.track_number = play.get("track_number")
                    state.total_tracks = play.get("total_tracks")
                    state.artist = play.get("artist")
                    state.album = play.get("album")
                    state.song = play.get("song")
                    state.album_art_url = play.get("album_art_url")

            # Poll timer mode
            timer_mode = await self.api.get_timer_mode()
            if timer_mode is not None:
                state.timer_mode = timer_mode

        return state
