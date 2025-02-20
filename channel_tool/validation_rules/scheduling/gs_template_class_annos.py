from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    get_nested,
    validation_rule,
)

"""
    Rules to check consistency of classification annotations in the GS templates
"""


def class_anno(channel_config: Dict[str, Any], key: str) -> Any:
    return get_nested(channel_config, ["classification_annotations", key])


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="DVBS2X-encoded space-ground SBand must have classification annotation space_ground_sband_dvbs2x_pls",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_dvbs2x_must_have_pls_value(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        class_anno(channel_config, "space_ground_sband")
        and class_anno(channel_config, "space_ground_sband_encoding") == "DVBS2X"
        and not class_anno(channel_config, "space_ground_sband_dvbs2x_pls")
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Space-ground SBand must have classification annotation space_ground_sband_bandwidth_mhz",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_must_have_bandwidth(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_anno(channel_config, "space_ground_sband") and not class_anno(
        channel_config, "space_ground_sband_bandwidth_mhz"
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Space-ground SBand must have classification annotation space_ground_sband_encoding",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_must_have_encoding(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_anno(channel_config, "space_ground_sband") and not class_anno(
        channel_config, "space_ground_sband_encoding"
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Space-ground SBand must have classification annotation space_ground_sband_mid_freq_mhz",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_sband_must_have_mid_freq(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_anno(channel_config, "space_ground_sband") and not class_anno(
        channel_config, "space_ground_sband_mid_freq_mhz"
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Space-ground XBand must have classification annotation space_ground_xband_dvbs2x_pls",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_have_pls_value(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_anno(channel_config, "space_ground_xband") and not class_anno(
        channel_config, "space_ground_xband_dvbs2x_pls"
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Space-ground XBand must have classification annotation space_ground_xband_bandwidth_mhz",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_have_bandwidth(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_anno(channel_config, "space_ground_xband") and not class_anno(
        channel_config, "space_ground_xband_bandwidth_mhz"
    ):
        return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Directionality classification annotation must be correct given the individual radio band booleans",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def directionality_must_match_radio_band_booleans(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    any_space_ground = (
        class_anno(channel_config, "space_ground_xband")
        or class_anno(channel_config, "space_ground_sband")
        or class_anno(channel_config, "space_ground_uhf")
    )
    any_ground_space = class_anno(channel_config, "ground_space_sband") or class_anno(
        channel_config, "ground_space_uhf"
    )
    class_anno_directionality = class_anno(channel_config, "directionality")
    if any_ground_space and any_space_ground:
        expected_directionality = "BIDIR"
    elif any_space_ground:
        expected_directionality = "TXO"
    elif any_ground_space:
        expected_directionality = "RXO"
    else:
        return "no radio band booleans are true, no directionality is applicable"
    if class_anno_directionality != expected_directionality:
        return f"directionality is {class_anno_directionality} but radio band booleans imply {expected_directionality}"
    return True
