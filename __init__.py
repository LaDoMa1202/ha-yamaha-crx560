"""Yamaha CRX-N560 Home Assistant Integration v3.0."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YamahaCrxN560dApi
from .coordinator import YamahaCrxN560dCoordinator
from .const import DOMAIN

PLATFORMS = ["media_player", "select", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = YamahaCrxN560dApi(session, entry.data[CONF_HOST])
    coordinator = YamahaCrxN560dCoordinator(hass, api)
    device_config = await api.get_device_config()
    if device_config:
        coordinator.device_config = device_config
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
