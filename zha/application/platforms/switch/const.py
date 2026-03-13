"""Constants for the switch platform."""

from enum import StrEnum

from zigpy.profiles import zha, zll


class SwitchDeviceClass(StrEnum):
    """Device class for switches."""

    OUTLET = "outlet"
    SWITCH = "switch"


OUTLET_PROFILE_DEVICE_TYPES = frozenset(
    {
        # ZHA
        (zha.PROFILE_ID, zha.DeviceType.MAIN_POWER_OUTLET),
        (zha.PROFILE_ID, zha.DeviceType.ON_OFF_PLUG_IN_UNIT),
        (zha.PROFILE_ID, zha.DeviceType.SMART_PLUG),
        # ZLL
        (zll.PROFILE_ID, zll.DeviceType.ON_OFF_PLUGIN_UNIT),
    }
)
