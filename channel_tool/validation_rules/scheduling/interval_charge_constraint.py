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
    scope=ValidationRuleScope.SATELLITE,
    description="Either all enabled channels should have electrical costs or none should",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def enabled_channels_electrical_costs_all_or_none(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id_to_config: Dict[str, Dict[str, Any]],
    channel_id_to_class_annos: Dict[str, Dict[str, Any]],
) -> Union[str, bool]:
    enabled_with_elec_costs = []
    enabled_without_elec_costs = []
    for channel_id, channel_config in channel_id_to_config.items():
        if channel_config["enabled"]:
            if (
                get_nested(channel_config, ["satellite_constraints", "electrical_cost"])
                == None
            ):
                enabled_without_elec_costs.append(channel_id)
            else:
                enabled_with_elec_costs.append(channel_id)
    num_with_elec = len(enabled_with_elec_costs)
    num_without_elec = len(enabled_without_elec_costs)
    if num_with_elec > 0 and num_without_elec > 0:
        return f"{num_with_elec} channels with elec. costs {enabled_with_elec_costs}, {num_without_elec} channels without elec. costs {enabled_without_elec_costs}"
    return True
