"""Test coordinator LED light support."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bellows.ezsp.xncp import FirmwareFeatures
import pytest

from tests.common import get_entity
from zha.application import Platform
from zha.application.gateway import Gateway
from zha.application.platforms.light import (
    DEFAULT_COORDINATOR_LED_XY_COLOR,
    CoordinatorLED,
    _xy_brightness_to_rgb,
)
from zha.application.platforms.light.const import ColorMode


async def test_coordinator_led_not_exposed_without_feature(
    zha_gateway: Gateway,
) -> None:
    """Test that the coordinator LED entity is not exposed without support."""
    with pytest.raises(KeyError):
        get_entity(
            zha_gateway.coordinator_zha_device,
            platform=Platform.LIGHT,
            exact_entity_type=CoordinatorLED,
        )


async def test_coordinator_led_entity(zha_data, zigpy_app_controller) -> None:
    """Test coordinator LED light discovery and control."""
    zigpy_app_controller.state.node_info.manufacturer = "Nabu Casa"
    zigpy_app_controller.state.node_info.model = "Home Assistant Connect ZBT-2"
    zigpy_app_controller._ezsp = SimpleNamespace(
        _xncp_features=FirmwareFeatures.LED_CONTROL,
        xncp_set_led_state=AsyncMock(),
    )

    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.new",
            return_value=zigpy_app_controller,
        ),
        patch(
            "bellows.zigbee.application.ControllerApplication",
            return_value=zigpy_app_controller,
        ),
    ):
        gateway = await Gateway.async_from_config(zha_data)
        await gateway.async_initialize()
        await gateway.async_block_till_done()
        await gateway.async_initialize_devices_and_entities()

    try:
        coordinator = gateway.coordinator_zha_device
        entity = get_entity(
            coordinator,
            platform=Platform.LIGHT,
            exact_entity_type=CoordinatorLED,
        )

        assert entity.state["on"] is False
        assert entity.state["color_mode"] == ColorMode.XY
        assert entity.state["supported_color_modes"] == {ColorMode.XY}

        await entity.async_turn_on(brightness=128)
        await gateway.async_block_till_done()

        expected_red, expected_green, expected_blue = _xy_brightness_to_rgb(
            DEFAULT_COORDINATOR_LED_XY_COLOR[0],
            DEFAULT_COORDINATOR_LED_XY_COLOR[1],
            128,
        )
        assert zigpy_app_controller._ezsp.xncp_set_led_state.await_args_list[
            0
        ].kwargs == {
            "red": expected_red,
            "green": expected_green,
            "blue": expected_blue,
        }
        assert entity.state["on"] is True
        assert entity.state["brightness"] == 128
        assert entity.state["color_mode"] == ColorMode.XY

        await entity.async_turn_off()
        await gateway.async_block_till_done()

        assert zigpy_app_controller._ezsp.xncp_set_led_state.await_args_list[
            1
        ].kwargs == {
            "red": 0,
            "green": 0,
            "blue": 0,
        }
        assert entity.state["on"] is False
    finally:
        await gateway.shutdown()
        await asyncio.sleep(0)


async def test_coordinator_led_brightness_uses_current_xy_color(
    zha_data, zigpy_app_controller
) -> None:
    """Test that brightness-only updates preserve the current XY color."""
    zigpy_app_controller.state.node_info.manufacturer = "Nabu Casa"
    zigpy_app_controller.state.node_info.model = "Home Assistant Connect ZBT-2"
    zigpy_app_controller._ezsp = SimpleNamespace(
        _xncp_features=FirmwareFeatures.LED_CONTROL,
        xncp_set_led_state=AsyncMock(),
    )

    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.new",
            return_value=zigpy_app_controller,
        ),
        patch(
            "bellows.zigbee.application.ControllerApplication",
            return_value=zigpy_app_controller,
        ),
    ):
        gateway = await Gateway.async_from_config(zha_data)
        await gateway.async_initialize()
        await gateway.async_block_till_done()
        await gateway.async_initialize_devices_and_entities()

    try:
        entity = get_entity(
            gateway.coordinator_zha_device,
            platform=Platform.LIGHT,
            exact_entity_type=CoordinatorLED,
        )

        red_xy = (0.64, 0.33)
        await entity.async_turn_on(xy_color=red_xy, brightness=255)
        await gateway.async_block_till_done()

        await entity.async_turn_on(brightness=64)
        await gateway.async_block_till_done()

        assert zigpy_app_controller._ezsp.xncp_set_led_state.await_args_list[
            1
        ].kwargs == {
            "red": 64,
            "green": 22,
            "blue": 11,
        }
        assert entity.state["xy_color"] == red_xy
        assert entity.state["brightness"] == 64
    finally:
        await gateway.shutdown()
        await asyncio.sleep(0)


async def test_coordinator_led_restores_attributes_and_replays_on_state(
    zha_data, zigpy_app_controller
) -> None:
    """Test that coordinator LED restoration replays the previous on-state."""
    zigpy_app_controller.state.node_info.manufacturer = "Nabu Casa"
    zigpy_app_controller.state.node_info.model = "Home Assistant Connect ZBT-2"
    zigpy_app_controller._ezsp = SimpleNamespace(
        _xncp_features=FirmwareFeatures.LED_CONTROL,
        xncp_set_led_state=AsyncMock(),
    )

    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.new",
            return_value=zigpy_app_controller,
        ),
        patch(
            "bellows.zigbee.application.ControllerApplication",
            return_value=zigpy_app_controller,
        ),
    ):
        gateway = await Gateway.async_from_config(zha_data)
        await gateway.async_initialize()
        await gateway.async_block_till_done()
        await gateway.async_initialize_devices_and_entities()

    try:
        entity = get_entity(
            gateway.coordinator_zha_device,
            platform=Platform.LIGHT,
            exact_entity_type=CoordinatorLED,
        )

        entity.restore_external_state_attributes(
            state=True,
            off_with_transition=False,
            off_brightness=None,
            brightness=80,
            color_temp=None,
            xy_color=(0.64, 0.33),
            color_mode=ColorMode.XY,
            effect=None,
        )
        await gateway.async_block_till_done()

        expected_red, expected_green, expected_blue = _xy_brightness_to_rgb(
            0.64,
            0.33,
            80,
        )
        assert zigpy_app_controller._ezsp.xncp_set_led_state.await_args_list[
            0
        ].kwargs == {
            "red": expected_red,
            "green": expected_green,
            "blue": expected_blue,
        }
        assert entity.state["on"] is True
        assert entity.state["brightness"] == 80
        assert entity.state["xy_color"] == (0.64, 0.33)
        assert entity.state["color_mode"] == ColorMode.XY
    finally:
        await gateway.shutdown()
        await asyncio.sleep(0)
