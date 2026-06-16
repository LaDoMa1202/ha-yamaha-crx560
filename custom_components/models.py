"""Data models for Yamaha CRX-N560 integration."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class YamahaState:
    """Combined state of the Yamaha receiver."""

    # System / Basic Status
    power: str = "Standby"
    sleep: str = "Off"
    volume: int = 0
    muted: bool = False
    input_sel: str = "CD"

    # Player / Play Info
    playback_info: str = "Stop"
    shuffle: bool = False
    repeat: str = "Off"
    play_time: Optional[int] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    song: Optional[str] = None
    album_art_url: Optional[str] = None

    # Tuner
    band: str = "FM"
    tuner_preset: Optional[int] = None
    tuner_freq: Optional[int] = None
    tuner_tuned: bool = False
    tuner_program_type: Optional[str] = None
    tuner_program_service: Optional[str] = None
    tuner_radio_text_a: Optional[str] = None
    tuner_radio_text_b: Optional[str] = None

    # Alarm Timer
    timer_mode: str = "Off"
    timer_start_time: Optional[str] = None
    timer_volume: Optional[int] = None
    timer_repeat: str = "Once"
