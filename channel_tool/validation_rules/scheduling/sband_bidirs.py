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
    Rules related to S-Band-down BIDIRs
"""


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Transmit times elevation must exist and match innermost link profile min elevation",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_transmit_times_elevation_exists_and_matches_innermost_link_profile_min_elevation(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if (
        not class_annos["space_ground_uhf"]
        or not class_annos["ground_space_uhf"]
        or not class_annos["space_ground_sband"]
    ):
        return True

    link_profiles = get_nested(channel_config, ["link_profile"])

    link_profile = max(link_profiles, key=lambda x: x["downlink_rate_kbps"])

    if "default_min_elevation_deg" in link_profile:
        if "add_transmit_times" not in link_profile:
            return "S-Band BIDIRs that adhere to the new schema must contain `add_transmit_times`"

        return True

    min_elevation_deg = link_profile["min_elevation_deg"]
    dynamic_param_elevation = get_nested(
        channel_config,
        ["dynamic_window_parameters", "transmit_times", "elevation_threshold_deg"],
    )

    if not dynamic_param_elevation:
        return "S-Band BIDIRs must have transmit times min elevation"

    if min_elevation_deg == dynamic_param_elevation:
        return True

    return f"{min_elevation_deg} is not equal to {dynamic_param_elevation}"
