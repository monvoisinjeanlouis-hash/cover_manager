"""Capteur indiquant la règle active et la raison."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RULE_DAY, RULE_HEAT, RULE_NIGHT, RULE_PAUSED


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RuleSensor(hass.data[DOMAIN][entry.entry_id], entry)])


class RuleSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Règle active"
    _attr_icon = "mdi:format-list-checks"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [RULE_PAUSED, RULE_NIGHT, RULE_DAY, RULE_HEAT]

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_rule"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            manufacturer="Cover_Manager",
        )

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("rule")

    @property
    def extra_state_attributes(self):
        # Attributs pratiques pour les automatisations, tableaux de bord et diagnostics.
        d = self.coordinator.data or {}
        return {
            "position_cible": d.get("target"),
            "raison": d.get("reason"),
            "fermeture_bloquee_par": d.get("blocked_by"),
        }
