from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    get_nested,
    validation_rule,
)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="tracking_target should not be defined in a GS template channel",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def groundstation_template_should_not_define_tracking_target(
    input: ValidationRuleInput,
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


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="tracking_target should not be defined in a satellite template channel",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_template_should_not_define_tracking_target(
    input: ValidationRuleInput,
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


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is TRACK then tracking_target config should be specified",
    mode=ValidationRuleMode.ENFORCE,
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
    description="If adcs_pointing is not TRACK then tracking_target config should not be specified",
    mode=ValidationRuleMode.ENFORCE,
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
