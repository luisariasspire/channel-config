from typing import Any, Dict, Optional, Union

from channel_tool.naming import class_annos_to_name
from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    get_nested,
    validation_rule,
)


#
@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Check that each SBAND channel has a HALFTRACK version with the correct adcs_pointing in gs templates",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_for_sband_gs_templates(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if channel_id.startswith("S_") and not channel_id.endswith("_HALFTRACK"):
        ht_channel = input.gs_templates.get(f"{channel_id}_HALFTRACK")
        if not ht_channel:
            return f"No SBAND HALFTRACK channel {channel_id} present. Every SBAND channel needs a HALFTRACK version."
        if ht_channel["classification_annotations"].get("adcs_pointing") != "HALFTRACK":
            return f"SBAND HALFTRACK channel {channel_id}_HALFTRACK does not have the correct adcs_pointing classification annotation."
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Check that each SBAND channel has a HALFTRACK version with the correct adcs_pointing in gs",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_for_sband_gs(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if channel_id.startswith("S_") and not channel_id.endswith("_HALFTRACK"):
        # The GS should be present in configs.
        ht_channel = input.gs_configs[gs_id].get(f"{channel_id}_HALFTRACK")
        if not ht_channel:
            return f"No SBAND HALFTRACK channel {channel_id} present. Every SBAND channel needs a HALFTRACK version."
        if ht_channel["classification_annotations"].get("adcs_pointing") != "HALFTRACK":
            return f"SBAND HALFTRACK channel {channel_id}_HALFTRACK does not have the correct adcs_pointing classification annotation."
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="Check that each SBAND channel has a HALFTRACK version in sat templates",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_for_sband_sat_templates(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if channel_id.startswith("S_") and not channel_id.endswith("_HALFTRACK"):
        ht_channel = input.sat_templates.get(f"{channel_id}_HALFTRACK")
        if not ht_channel:
            return f"No SBAND HALFTRACK channel {channel_id} present. Every SBAND channel needs a HALFTRACK version."
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Check that for any HALFTRACK channel, the adcs_config must have mode NADIRPOINTLATLON in gs templates",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_adcs_mode_gs_templates(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("adcs_pointing") == "HALFTRACK":
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if not adcs_config:
            return f"HALFTRACK channel {channel_id} needs an adcs_config"
        if adcs_config.get("mode") != "NADIRPOINTLATLON":
            return f"HALFTRACK channel {channel_id} should have adcs_config mode: NADIRPOINTLATLON"
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Check that for any HALFTRACK channel, the adcs_config must have mode NADIRPOINTLATLON in gs",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_adcs_mode_gs(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("adcs_pointing") == "HALFTRACK":
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if not adcs_config:
            return f"HALFTRACK channel {channel_id} needs an adcs_config"
        if adcs_config.get("mode") != "NADIRPOINTLATLON":
            return f"HALFTRACK channel {channel_id} should have adcs_config mode: NADIRPOINTLATLON"
    return True


# We don't want the same validation for sat_templates, because each ADCS_CONFIG will be unique to the satellite.
@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Check that for any HALFTRACK channel, the adcs_config must have an adcs_config in sat",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_halftrack_consistency_adcs_instrument_sat(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if class_annos.get("adcs_pointing") == "HALFTRACK":
        adcs_config = get_nested(channel_config, ["window_parameters", "adcs_config"])
        if not adcs_config:
            return f"HALFTRACK channel {channel_id} needs an adcs_config"
        if not adcs_config.get("primary_instrument"):
            return f"HALFTRACK channel {channel_id} should have adcs_config primary instrument configured."
        if not adcs_config.get("secondary_instrument"):
            return f"HALFTRACK channel {channel_id} should have adcs_config secondary instrument configured."
    return True
