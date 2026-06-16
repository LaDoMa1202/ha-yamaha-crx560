"""Select platform for Yamaha CRX-N560 Sleep Timer."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SLEEP_VALUES, MODEL, MANUFACTURER
from .coordinator import YamahaCrxN560dCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yamaha sleep timer select."""
    coordinator: YamahaCrxN560dCoordinator = entry.runtime_data
    async_add_entities([YamahaSleepTimerSelect(coordinator, entry)])


class YamahaSleepTimerSelect(CoordinatorEntity, SelectEntity):
    """Select entity for Yamaha sleep timer."""

    _attr_icon = "mdi:timer-outline"
    _attr_options = SLEEP_VALUES
    _attr_has_entity_name = True
    _attr_translation_key = "sleep_timer"

    def __init__(self, coordinator: YamahaCrxN560dCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_sleep_timer"
        self._attr_name = "Sleep Timer"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or MODEL,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }

    @property
    def current_option(self) -> str | None:
        """Return current sleep timer value."""
        if self.coordinator.data:
            return self.coordinator.data.sleep or "Off"
        return "Off"

    async def async_select_option(self, option: str) -> None:
        """Set sleep timer."""
        await self.coordinator.api.set_sleep(option)
        await self.coordinator.async_request_refresh()
