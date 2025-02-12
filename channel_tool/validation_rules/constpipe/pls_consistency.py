from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)

# Rules to enforce that the effective DVBS2X PLS matches what's in the classification annotations.
# PLS value is a fundamental part of the channel definition, so there's no use case for overriding
# it to be something that doesn't match. To use a different PLS, create a new channel.
# GS-side config must override PLS to match the channel PLS if that channel PLS is different from
# the bandaid default for that radio band.
# Satellite-side config need not override PLS, but if it does, the value must match the channel PLS.


def get_pls_configured_value(channel_config: Dict[str, Any], radio_band: str) -> Any:
    forward_channels = channel_config.get("window_parameters", {}).get(
        "forward_channels", []
    )
    # if there is a single forward channel with an unnamed or the correct radio_band,
    # this is the band's forward channel
    if (
        len(forward_channels) == 1
        and forward_channels[0].get("radio_band", radio_band) == radio_band
    ):
        band_forward_channel = forward_channels[0]
    else:
        # otherwise find the forward channel with the correct radio_band
        band_forward_channel = next(
            filter(lambda ch: ch.get("radio_band") == radio_band, forward_channels),
            None,
        )
    if band_forward_channel:
        return band_forward_channel.get("bandaid_override", {}).get("pls")
    return None


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="GS SBand down DVBS2X PLS value from classification annotation must match effective value",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_channel_sband_down_dvbs2x_class_anno_pls_must_match_effective_pls(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        class_annos.get("space_ground_sband")
        and class_annos.get("space_ground_sband_encoding") == "DVBS2X"
    ):
        class_anno_pls = class_annos.get("space_ground_sband_dvbs2x_pls")
        default_pls = 39  # default PLS for SBand if not configured
        # see https://github.ect.spire.com/space/spire-radio/blob/19bb2a1bad26e54076ad28d49b13bbd5aa406a16/bandaid/config/dexter.json#L174
        effective_pls = get_pls_configured_value(channel_config, "SBAND") or default_pls
        if effective_pls == class_anno_pls:
            return True
        else:
            return f"annotation PLS {class_anno_pls}, effective PLS {effective_pls}"
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="GS XBand down DVBS2X PLS value from classification annotation must match effective value",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_channel_xband_down_dvbs2x_class_anno_pls_must_match_effective_pls(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("space_ground_xband"):
        class_anno_pls = class_annos.get("space_ground_xband_dvbs2x_pls")
        default_pls = 5  # default PLS for XBand if not configured
        # see https://github.ect.spire.com/space/spire-radio/blob/19bb2a1bad26e54076ad28d49b13bbd5aa406a16/bandaid/config/dexter.json#L216
        effective_pls = get_pls_configured_value(channel_config, "XBAND") or default_pls
        if effective_pls == class_anno_pls:
            return True
        else:
            return f"annotation PLS {class_anno_pls}, effective PLS {effective_pls}"
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Satellite SBand down DVBS2X PLS value from classification annotation must match any configured value",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_channel_sband_down_dvbs2x_class_anno_pls_must_match_any_configured_pls(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        class_annos.get("space_ground_sband")
        and class_annos.get("space_ground_sband_encoding") == "DVBS2X"
    ):
        class_anno_pls = class_annos.get("space_ground_sband_dvbs2x_pls")
        configured_pls = get_pls_configured_value(channel_config, "SBAND")
        if configured_pls == None or configured_pls == class_anno_pls:
            return True
        else:
            return f"annotation PLS {class_anno_pls}, configured PLS {configured_pls}"
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Satellite XBand down DVBS2X PLS value from classification annotation must match any configured value",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_channel_xband_down_dvbs2x_class_anno_pls_must_match_any_configured_pls(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("space_ground_xband"):
        class_anno_pls = class_annos.get("space_ground_xband_dvbs2x_pls")
        configured_pls = get_pls_configured_value(channel_config, "XBAND")
        if configured_pls == None or configured_pls == class_anno_pls:
            return True
        else:
            return f"annotation PLS {class_anno_pls}, configured PLS {configured_pls}"
    return True
