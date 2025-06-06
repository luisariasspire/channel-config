from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleEnv,
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    get_nested,
    validation_rule,
)


# To be deprecated
@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="tracking_target should not be defined in a satellite channel",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_should_not_define_tracking_target(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    tracking_target_config = get_nested(
        channel_config, ["window_parameters", "tracking_target"]
    )
    if tracking_target_config != None:
        return False
    return True


# To be deprecated
@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is TRACK, then tracking_target config should be specified",
    mode=ValidationRuleMode.ENFORCE,
    env=ValidationRuleEnv.PRODUCTION_ONLY,
)  # type: ignore
def adcs_pointing_track_implies_tracking_target_config(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("adcs_pointing") == "TRACK":
        tracking_target_config = get_nested(
            channel_config, ["window_parameters", "tracking_target"]
        )
        if tracking_target_config == None:
            return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is TRACK or HALFTRACK then adcs_config config should be specified",
    mode=ValidationRuleMode.ENFORCE,
    env=ValidationRuleEnv.STAGING_ONLY,
)  # type: ignore
def adcs_pointing_track_implies_adcs_config_config(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    pointing_annots = ["TRACK", "HALFTRACK"]
    if class_annos.get("adcs_pointing") in pointing_annots:
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if adcs_config == None:
            return False
    return True


# To be deprecated
@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is not TRACK then tracking_target config should not be specified",
    mode=ValidationRuleMode.ENFORCE,
    env=ValidationRuleEnv.PRODUCTION_ONLY,
)  # type: ignore
def adcs_pointing_not_track_implies_no_tracking_target_config(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("adcs_pointing") != "TRACK":
        tracking_target_config = get_nested(
            channel_config, ["window_parameters", "tracking_target"]
        )
        if tracking_target_config != None:
            return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is not TRACK or HALFTRACK then adcs_config config should not be specified",
    mode=ValidationRuleMode.ENFORCE,
    env=ValidationRuleEnv.STAGING_ONLY,
)  # type: ignore
def adcs_pointing_not_track_implies_no_adcs_config(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    pointing_annots = ["TRACK", "HALFTRACK"]
    if class_annos.get("adcs_pointing") not in pointing_annots:
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if adcs_config != None:
            return False
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="adcs_config_target_coords should only be specified when adcs_config is present.",
    mode=ValidationRuleMode.ENFORCE,
    env=ValidationRuleEnv.STAGING_ONLY,
)  # type: ignore
def dynamic_adcs_coords_should_only_be_set_if_adcs_config_present(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if get_nested(
        channel_config, ["dynamic_window_parameters", "adcs_config_target_coords"]
    ):
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if not adcs_config:
            return False
    return True
