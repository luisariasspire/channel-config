from typing import Any, Dict, Optional

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleViolatedError,
    class_anno,
    get_nested,
    validation_rule,
)


@validation_rule(
    scope="groundstation_channel",
    description="DVBS2X-encoded space-ground SBand must have classification annotation space_ground_sband_dvbs2x_pls",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_dvbs2x_must_have_pls_value(
    gs_id: str,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> bool:
    if (
        class_anno(channel_config, "space_ground_sband")
        and class_anno(channel_config, "space_ground_sband_encoding") == "DVBS2X"
        and not class_anno(channel_config, "space_ground_sband_dvbs2x_pls")
    ):
        return False
    return True


@validation_rule(
    scope="groundstation_channel",
    description="Space-ground SBand must have classification annotation space_ground_sband_bandwidth_mhz",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_must_have_bandwidth(
    gs_id: str,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> bool:
    if class_anno(channel_config, "space_ground_sband") and not class_anno(
        channel_config, "space_ground_sband_bandwidth_mhz"
    ):
        return False
    return True


@validation_rule(
    scope="groundstation_channel",
    description="Space-ground XBand must have classification annotation space_ground_xband_dvbs2x_pls",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_have_pls_value(
    gs_id: str,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> bool:
    if class_anno(channel_config, "space_ground_xband") and not class_anno(
        channel_config, "space_ground_xband_dvbs2x_pls"
    ):
        return False
    return True


@validation_rule(
    scope="groundstation_channel",
    description="Space-ground XBand must have classification annotation space_ground_xband_bandwidth_mhz",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_have_bandwidth(
    gs_id: str,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> bool:
    if class_anno(channel_config, "space_ground_xband") and not class_anno(
        channel_config, "space_ground_xband_bandwidth_mhz"
    ):
        return False
    return True
