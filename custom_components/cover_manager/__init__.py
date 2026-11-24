"""Intégration Cover_Manager."""
from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CoverManagerConfigEntry, CoverManagerCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: CoverManagerConfigEntry
) -> bool:
    # Le coordinateur centralise l'évaluation des règles et les appels aux volets.
    coordinator = CoverManagerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.async_start_listeners()
    entry.async_on_unload(coordinator.async_stop_listeners)

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("%s : intégration démarrée", entry.title)
    return True


async def _async_reload(
    hass: HomeAssistant, entry: CoverManagerConfigEntry
) -> None:
    _LOGGER.info("%s : rechargement après modification des options", entry.title)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: CoverManagerConfigEntry
) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        _LOGGER.info("%s : intégration arrêtée", entry.title)
    return unloaded
