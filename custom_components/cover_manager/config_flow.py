"""Config flow + options flow."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)

from .const import *  # noqa: F403
from .const import DEFAULTS, DOMAIN


def _num(min_, max_, step=1, unit=None):
    """Construit un sélecteur numérique avec ses bornes et son unité."""
    return NumberSelector(
        NumberSelectorConfig(
            min=min_, max=max_, step=step, mode=NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _suggest(o, key):
    """Propose la valeur enregistrée sans imposer sa présence dans les options."""
    return {"suggested_value": o.get(key)}


def _options_schema(o: dict) -> vol.Schema:
    d = lambda k: o.get(k, DEFAULTS[k])  # noqa: E731
    return vol.Schema(
        {
            vol.Required(CONF_COVERS, default=o.get(CONF_COVERS, [])): EntitySelector(
                EntitySelectorConfig(domain="cover", multiple=True)
            ),
            vol.Required(CONF_OPEN_TIME, default=d(CONF_OPEN_TIME)): TimeSelector(),
            vol.Required(CONF_CLOSE_TIME, default=d(CONF_CLOSE_TIME)): TimeSelector(),
            vol.Optional(CONF_OPEN_TIME_WE, description=_suggest(o, CONF_OPEN_TIME_WE)): TimeSelector(),
            vol.Optional(CONF_CLOSE_TIME_WE, description=_suggest(o, CONF_CLOSE_TIME_WE)): TimeSelector(),
            vol.Optional(CONF_LUX_SENSOR, description=_suggest(o, CONF_LUX_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="illuminance")
            ),
            vol.Optional(CONF_LUX_OPEN, default=d(CONF_LUX_OPEN)): _num(0, 100000, 10, "lx"),
            vol.Optional(CONF_LUX_CLOSE, default=d(CONF_LUX_CLOSE)): _num(0, 100000, 10, "lx"),
            vol.Optional(CONF_LUX_DELAY, default=d(CONF_LUX_DELAY)): _num(0, 120, 1, "min"),
            vol.Optional(CONF_TEMP_SENSOR, description=_suggest(o, CONF_TEMP_SENSOR)): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_HEAT_THRESHOLD, default=d(CONF_HEAT_THRESHOLD)): _num(10, 45, 0.5, "°C"),
            vol.Optional(CONF_HEAT_POSITION, default=d(CONF_HEAT_POSITION)): _num(0, 100, 5, "%"),
            vol.Optional(CONF_AZIMUTH_MIN, default=d(CONF_AZIMUTH_MIN)): _num(0, 360, 1, "°"),
            vol.Optional(CONF_AZIMUTH_MAX, default=d(CONF_AZIMUTH_MAX)): _num(0, 360, 1, "°"),
            vol.Optional(CONF_MIN_ELEVATION, default=d(CONF_MIN_ELEVATION)): _num(0, 90, 1, "°"),
            vol.Optional(CONF_WINDOW_SENSORS, description=_suggest(o, CONF_WINDOW_SENSORS)): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
        }
    )


class VoletsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["name"], data={CONF_COVERS: user_input[CONF_COVERS]}
            )
        schema = vol.Schema(
            {
                vol.Required("name", default="Volets"): str,
                vol.Required(CONF_COVERS): EntitySelector(
                    EntitySelectorConfig(domain="cover", multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return VoletsOptionsFlow()


class VoletsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_options_schema(current))
