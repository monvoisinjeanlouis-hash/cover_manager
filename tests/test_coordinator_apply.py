"""Tests de l'application des cibles aux volets."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.components.cover import CoverEntityFeature

from custom_components.cover_manager.coordinator import CoverManagerCoordinator


class ApplyTargetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cover = "cover.test"
        self.state = SimpleNamespace(
            state="open",
            attributes={
                "current_position": 100,
                "supported_features": CoverEntityFeature.SET_POSITION,
            },
        )
        self.services = SimpleNamespace(async_call=AsyncMock())
        self.coordinator = SimpleNamespace(
            covers=[self.cover],
            _applied={},
            hass=SimpleNamespace(
                states=SimpleNamespace(get=Mock(return_value=self.state)),
                services=self.services,
            ),
        )

    async def apply(self, target, windows=None):
        await CoverManagerCoordinator._apply(self.coordinator, target, windows or [])

    async def test_open_cover_already_at_target_is_not_commanded(self):
        await self.apply(100)
        self.services.async_call.assert_not_awaited()
        self.assertEqual(self.coordinator._applied[self.cover], 100)

    async def test_closed_and_partial_positions_are_not_commanded(self):
        for position, state in ((0, "closed"), (30, "open")):
            with self.subTest(position=position):
                self.coordinator._applied.clear()
                self.state.state = state
                self.state.attributes["current_position"] = position
                await self.apply(position)
                self.services.async_call.assert_not_awaited()
                self.assertEqual(self.coordinator._applied[self.cover], position)

    async def test_open_without_position_is_not_commanded(self):
        self.state.attributes.pop("current_position")
        await self.apply(100)
        self.services.async_call.assert_not_awaited()

    async def test_closed_without_position_is_not_commanded(self):
        self.state.attributes.pop("current_position")
        self.state.state = "closed"
        await self.apply(0)
        self.services.async_call.assert_not_awaited()

    async def test_partial_position_is_not_inferred_from_open_state(self):
        self.state.attributes.pop("current_position")
        await self.apply(30)
        self.services.async_call.assert_awaited_once()

    async def test_cover_moving_away_from_target_receives_command(self):
        self.state.state = "closing"
        await self.apply(100)
        self.services.async_call.assert_awaited_once()

    async def test_partial_cover_receives_open_command(self):
        self.state.attributes["current_position"] = 30
        await self.apply(100)
        self.services.async_call.assert_awaited_once()

    async def test_manual_change_is_respected_until_target_changes(self):
        await self.apply(100)
        self.state.attributes["current_position"] = 50
        await self.apply(100)
        self.services.async_call.assert_not_awaited()
        await self.apply(0)
        self.services.async_call.assert_awaited_once()

    async def test_open_window_blocks_closing_then_retries(self):
        await self.apply(0, ["binary_sensor.window"])
        self.services.async_call.assert_not_awaited()
        self.assertNotIn(self.cover, self.coordinator._applied)
        await self.apply(0)
        self.services.async_call.assert_awaited_once()

    async def test_unavailable_cover_is_retried(self):
        self.state.state = "unavailable"
        await self.apply(100)
        self.services.async_call.assert_not_awaited()
        self.assertNotIn(self.cover, self.coordinator._applied)
        self.state.state = "closed"
        self.state.attributes["current_position"] = 0
        await self.apply(100)
        self.services.async_call.assert_awaited_once()

    async def test_reset_cache_does_not_repeat_command_at_target(self):
        await self.apply(100)
        self.coordinator._applied.clear()
        await self.apply(100)
        self.services.async_call.assert_not_awaited()

    async def test_disabled_position_control_uses_open_and_close(self):
        self.state.attributes["supported_features"] = 0
        self.state.attributes["current_position"] = 0
        self.state.state = "closed"
        await self.apply(100)
        self.services.async_call.assert_awaited_once_with(
            "cover", "open_cover", {"entity_id": self.cover}
        )
