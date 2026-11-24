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

    async def test_command_is_logged_without_claiming_completion(self):
        self.state.attributes["current_position"] = 30
        with self.assertLogs("custom_components.cover_manager.coordinator", level="INFO") as logs:
            await self.apply(100)
        self.assertIn("cover.test : position 100 % demandée", logs.output[0])

    async def test_unsupported_intermediate_position_is_logged(self):
        self.state.attributes["supported_features"] = 0
        with self.assertLogs("custom_components.cover_manager.coordinator", level="WARNING") as logs:
            await self.apply(30)
        self.assertIn("cover.test ne gère pas la position : 30 % ignoré", logs.output[0])
        self.services.async_call.assert_not_awaited()

    async def test_blocked_closure_is_logged_at_debug(self):
        with self.assertLogs("custom_components.cover_manager.coordinator", level="DEBUG") as logs:
            await self.apply(0, ["binary_sensor.window"])
        self.assertIn("fermeture de 100 % à 0 % bloquée", logs.output[0])


class SensorLogTests(unittest.TestCase):
    def setUp(self):
        self.entity_id = "sensor.luminosite"
        self.state = SimpleNamespace(state="unavailable")
        self.coordinator = SimpleNamespace(
            entry=SimpleNamespace(title="Salon"),
            hass=SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=self.state))),
            _sensor_problems={},
        )

    def read_sensor(self):
        return CoverManagerCoordinator._float(self.coordinator, self.entity_id)

    def test_sensor_warnings_are_deduplicated_and_recovery_logged(self):
        with self.assertLogs("custom_components.cover_manager.coordinator", level="INFO") as logs:
            self.assertIsNone(self.read_sensor())
            self.assertIsNone(self.read_sensor())
            self.state.state = "invalid"
            self.assertIsNone(self.read_sensor())
            self.assertIsNone(self.read_sensor())
            self.state.state = "500"
            self.assertEqual(self.read_sensor(), 500)
            self.assertEqual(self.read_sensor(), 500)
        self.assertEqual(len(logs.output), 3)
        self.assertIn("absent ou indisponible", logs.output[0])
        self.assertIn("valeur non numérique", logs.output[1])
        self.assertIn("à nouveau utilisable", logs.output[2])


class EvaluationLogTests(unittest.IsolatedAsyncioTestCase):
    async def test_rule_changes_are_logged_only_when_rule_or_target_changes(self):
        coordinator = SimpleNamespace(
            enabled=True,
            entry=SimpleNamespace(title="Salon"),
            data=None,
            _evaluate=Mock(return_value=(100, "day", "plage horaire de jour")),
            _windows_open=Mock(return_value=[]),
            _apply=AsyncMock(),
        )
        with self.assertLogs("custom_components.cover_manager.coordinator", level="INFO") as logs:
            coordinator.data = await CoverManagerCoordinator._async_update_data(coordinator)
            coordinator.data = await CoverManagerCoordinator._async_update_data(coordinator)
            coordinator._evaluate.return_value = (30, "heat", "soleil")
            await CoverManagerCoordinator._async_update_data(coordinator)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("règle day, cible 100 %", logs.output[0])
        self.assertIn("règle heat, cible 30 %", logs.output[1])
