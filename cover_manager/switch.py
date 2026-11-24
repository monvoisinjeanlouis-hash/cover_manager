"""Interrupteur d'activation de l'automatisme."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VoletsSwitch(hass.data[DOMAIN][entry.entry_id], entry)])


class VoletsSwitch(RestoreEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Automatisme actif"
    _attr_icon = "mdi:window-shutter-auto"

    def __init__(self, coordinator, entry):
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            manufacturer="Cover_Manager",
        )

    @property
    def is_on(self) -> bool:
        return self._coordinator.enabled

    async def async_added_to_hass(self) -> None:
        if (last := await self.async_get_last_state()) is not None:
            self._coordinator.enabled = last.state != "off"
            await self._coordinator.async_request_refresh()

    async def _set(self, value: bool) -> None:
        # Réinitialiser les cibles permet de reprendre immédiatement après une pause.
        self._coordinator.enabled = value
        self._coordinator.reset_applied()  # resynchronise à la réactivation
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
