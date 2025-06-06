from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)


# This logic covers two aspects of window parameter forward channel / reverse channel
# -- are the radio bands consistent with the classification annotations
# -- are the radio bands in a predictable order
# The predictable order is important because the contact scheduler merge logic is unaware of bands
# and will just merge GS element 0 with FM element 0, element 1 with 1 etc.
def check_consistent_radio_bands(
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    # This guard restricts the rule to S/U bidirs for now
    # It's super important as S/U bidirs have two forward channels.
    # It would be of value to remove the guard and extend to all channel types
    # However that's not possible at the moment as there is poor consistency around
    # whether the forward / reverse channels are defined on GS and/or FM side
    # and whether they are labelled with radio_band.
    if (
        not class_annos["space_ground_uhf"]
        or not class_annos["space_ground_sband"]
        or not class_annos["ground_space_uhf"]
    ):
        return True

    expected_forward_bands = []
    if class_annos["space_ground_uhf"]:
        expected_forward_bands.append("UHF")
    if class_annos["space_ground_sband"]:
        expected_forward_bands.append("SBAND")
    if class_annos["space_ground_xband"]:
        expected_forward_bands.append("XBAND")
    expected_reverse_bands = []
    if class_annos["ground_space_uhf"]:
        expected_reverse_bands.append("UHF")
    if class_annos["ground_space_sband"]:
        expected_reverse_bands.append("SBAND")

    expected_forward_bands.sort(
        reverse=True
    )  # reverse this to require [UHF, SBAND] order for S/U BIDIRs to avoid churn
    expected_reverse_bands.sort(reverse=True)

    window_params = channel_config.get("window_parameters", None)
    # allow no window parameters for now... but would be better to require them
    if not window_params:
        return True
    forward_channels = window_params.get("forward_channels", [])
    reverse_channels = window_params.get("reverse_channels", [])

    forward_bands = [
        channel["radio_band"]
        for channel in forward_channels
        if channel.get("radio_band")
    ]
    reverse_bands = [
        channel["radio_band"]
        for channel in reverse_channels
        if channel.get("radio_band")
    ]

    if (forward_bands, reverse_bands) != (
        expected_forward_bands,
        expected_reverse_bands,
    ):
        return f"Expected ordered forward/reverse channel radio bands {expected_forward_bands}/{expected_reverse_bands}"

    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Groundstation channel: radio bands are consistent with classification annotations",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def groundstation_channel_radio_bands_consistent_with_class_annos(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_consistent_radio_bands(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Satellite channel: radio bands are consistent with classification annotations",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_channel_radio_bands_consistent_with_class_annos(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_consistent_radio_bands(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Groundstation template channel: radio bands are consistent with classification annotations",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def groundstation_template_channel_radio_bands_consistent_with_class_annos(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_consistent_radio_bands(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="Satellite template channel: radio bands are consistent with classification annotations",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_template_channel_radio_bands_consistent_with_class_annos(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_consistent_radio_bands(class_annos, channel_config)
