"""Config flow for Yamaha CRX-N560D."""

import logging
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YamahaCrxN560dApi
from .const import DOMAIN, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


class YamahaCRXN560DConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                session = async_get_clientsession(self.hass)
                api = YamahaCrxN560dApi(session, host)
                if await api.get_basic_status() is not None:
                    await self.async_set_unique_id(f"crx_n560d_{host}")
                    self._abort_if_unique_id_configured()
                    name = user_input.get(CONF_NAME, DEFAULT_NAME)
                    return self.async_create_entry(title=name, data={CONF_HOST: host, CONF_NAME: name})
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        }), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if CONF_HOST in user_input:
                host = user_input[CONF_HOST]
                if host != self.config_entry.data.get(CONF_HOST):
                    session = async_get_clientsession(self.hass)
                    api = YamahaCrxN560dApi(session, host)
                    if await api.get_basic_status() is None:
                        errors["base"] = "cannot_connect"
                    else:
                        new_data = dict(self.config_entry.data)
                        new_data[CONF_HOST] = host
                        if CONF_NAME in user_input:
                            new_data[CONF_NAME] = user_input[CONF_NAME]
                        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            if not errors:
                return self.async_create_entry(title="", data={})

        ch = self.config_entry.data.get(CONF_HOST, "")
        cn = self.config_entry.data.get(CONF_NAME, DEFAULT_NAME)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=ch): str,
            vol.Required(CONF_NAME, default=cn): str,
        }), errors=errors)
