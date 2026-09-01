"""Tests for cluster configuration aggregation and resolution."""

from unittest.mock import MagicMock

import pytest
from zigpy.zcl import ReportingConfig

from zha.application.platforms import AttrConfig, ScaledReportingConfig
from zha.zigbee.cluster_config import AggregatedAttrConfig

VOLTAGE_SCALE = {
    "divisor_attributes": ("ac_voltage_divisor",),
    "multiplier_attributes": ("ac_voltage_multiplier",),
}
POWER_SCALE = {
    "divisor_attributes": ("ac_power_divisor", "power_divisor"),
    "multiplier_attributes": ("ac_power_multiplier", "power_multiplier"),
}


def _cluster(**cached: int | None) -> MagicMock:
    cluster = MagicMock()
    cluster.get.side_effect = cached.get
    return cluster


@pytest.mark.parametrize(
    ("cached", "change", "scale", "expected"),
    [
        # divisor 100: 1 V -> raw 100
        (
            {"ac_voltage_divisor": 100, "ac_voltage_multiplier": 1},
            1,
            VOLTAGE_SCALE,
            100,
        ),
        # divisor 10, fractional change: 0.05 -> raw 0.5 -> at least 1
        ({"ac_voltage_divisor": 10}, 0.05, VOLTAGE_SCALE, 1),
        # divisor 1000, fractional change: 0.05 -> raw 50
        ({"ac_voltage_divisor": 1000}, 0.05, VOLTAGE_SCALE, 50),
        # multiplier scales the other way
        (
            {"ac_voltage_divisor": 100, "ac_voltage_multiplier": 10},
            1,
            VOLTAGE_SCALE,
            10,
        ),
        # nothing cached: fall back to raw change
        ({}, 1, VOLTAGE_SCALE, 1),
        # zero divisor is treated as 1
        ({"ac_voltage_divisor": 0}, 1, VOLTAGE_SCALE, 1),
        # primary divisor missing, fallback divisor used
        ({"power_divisor": 10}, 1, POWER_SCALE, 10),
        # primary divisor wins over fallback
        ({"ac_power_divisor": 100, "power_divisor": 10}, 1, POWER_SCALE, 100),
    ],
)
def test_scaled_reporting_config_resolve(
    cached: dict[str, int], change: float, scale: dict, expected: int
) -> None:
    """Scaled reporting resolves to a raw change using cached scale attributes."""
    config = ScaledReportingConfig(
        min_interval=5, max_interval=900, reportable_change=change, **scale
    )
    assert config.scale_attributes == (
        scale["divisor_attributes"] + scale["multiplier_attributes"]
    )
    assert config.resolve(_cluster(**cached)) == ReportingConfig(
        min_interval=5, max_interval=900, reportable_change=expected
    )


def test_aggregated_attr_config_merges_raw_reporting() -> None:
    """Raw reporting configs merge to the tightest of each field."""
    agg = AggregatedAttrConfig()
    agg.merge(
        AttrConfig(
            read_on_startup=False,
            reporting=ReportingConfig(
                min_interval=30, max_interval=900, reportable_change=10
            ),
        )
    )
    agg.merge(
        AttrConfig(
            read_on_startup=True,
            reporting=ReportingConfig(
                min_interval=60, max_interval=300, reportable_change=20
            ),
        )
    )
    assert agg.read_on_startup is True
    assert agg.scaled_reporting is None
    assert agg.scale_attributes == ()
    assert agg.resolve_reporting(_cluster()) == ReportingConfig(
        min_interval=30, max_interval=300, reportable_change=10
    )


def test_aggregated_attr_config_merges_scaled_reporting() -> None:
    """Scaled reporting configs merge intervals/change and keep scale attributes."""
    agg = AggregatedAttrConfig()
    agg.merge(
        AttrConfig(
            read_on_startup=True,
            reporting=ScaledReportingConfig(
                min_interval=5, max_interval=900, reportable_change=1, **VOLTAGE_SCALE
            ),
        )
    )
    agg.merge(
        AttrConfig(
            read_on_startup=True,
            reporting=ScaledReportingConfig(
                min_interval=10,
                max_interval=600,
                reportable_change=0.5,
                **VOLTAGE_SCALE,
            ),
        )
    )
    assert agg.reporting is None
    assert agg.scaled_reporting == ScaledReportingConfig(
        min_interval=5, max_interval=600, reportable_change=0.5, **VOLTAGE_SCALE
    )
    assert agg.scale_attributes == ("ac_voltage_divisor", "ac_voltage_multiplier")
    assert agg.resolve_reporting(_cluster(ac_voltage_divisor=100)) == ReportingConfig(
        min_interval=5, max_interval=600, reportable_change=50
    )


def test_aggregated_attr_config_merges_scaled_with_raw_reporting() -> None:
    """A raw and a scaled config for the same attribute resolve to the tightest raw."""
    agg = AggregatedAttrConfig()
    agg.merge(
        AttrConfig(
            read_on_startup=True,
            reporting=ScaledReportingConfig(
                min_interval=5, max_interval=900, reportable_change=1, **VOLTAGE_SCALE
            ),
        )
    )
    agg.merge(
        AttrConfig(
            read_on_startup=False,
            reporting=ReportingConfig(
                min_interval=10, max_interval=300, reportable_change=20
            ),
        )
    )

    # scaled change (1 V * 100 = 100) is looser than the raw change (20)
    assert agg.resolve_reporting(_cluster(ac_voltage_divisor=100)) == ReportingConfig(
        min_interval=5, max_interval=300, reportable_change=20
    )

    # scaled change (1 V * 10 = 10) is tighter than the raw change (20)
    assert agg.resolve_reporting(_cluster(ac_voltage_divisor=10)) == ReportingConfig(
        min_interval=5, max_interval=300, reportable_change=10
    )


def test_aggregated_attr_config_no_reporting() -> None:
    """Attribute configs without reporting resolve to no reporting."""
    agg = AggregatedAttrConfig()
    agg.merge(AttrConfig(read_on_startup=True))
    assert agg.resolve_reporting(_cluster()) is None
