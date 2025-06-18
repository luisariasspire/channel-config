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


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="If adcs_pointing is TRACK or HALFTRACK then adcs_config config should be specified in GS templates",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def adcs_pointing_track_implies_adcs_config_config_gs_templates(
    input: ValidationRuleInput,
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


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="If adcs_pointing is TRACK or HALFTRACK then adcs_config config should be specified",
    mode=ValidationRuleMode.ENFORCE,
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


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="adcs_config_target_coords should only be specified when adcs_config is present.",
    mode=ValidationRuleMode.ENFORCE,
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
