"""Button platform for Yamaha CRX-N560 CD Tray."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODEL, MANUFACTURER
from .coordinator import YamahaCrxN560dCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yamaha tray button."""
    coordinator: YamahaCrxN560dCoordinator = entry.runtime_data
    async_add_entities([YamahaTrayButton(coordinator, entry)])


class YamahaTrayButton(ButtonEntity):
    """Button to toggle CD tray open/close."""

    _attr_icon = "mdi:disc-player"
    _attr_has_entity_name = True

    def __init__(self, coordinator: YamahaCrxN560dCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_cd_tray"
        self._attr_name = "CD Tray"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or MODEL,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    async def async_press(self) -> None:
        """Toggle the CD tray open/close."""
        await self._coordinator.api.toggle_tray()
