from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)


def check_xband_shared_set(
    class_annos: Dict[str, Any], channel_config: Dict[str, Any]
) -> bool:
    if class_annos["space_ground_xband"]:
        satellite_constraints = channel_config.get("satellite_constraints", {})
        sep_cons = satellite_constraints.get("separation", [])
        shared_set_refs = [
            con
            for con in sep_cons
            if con["type"] == "shared_constraint_set"
            and con["name"] == "spire_nasa_xband_coordination"
        ]
        return len(shared_set_refs) > 0
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Space-to-ground XBand separation constraints must use shared constraint set 'spire_nasa_xband_coordination'",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_enforce_spire_nasa_xband_coordination(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_xband_shared_set(class_annos, channel_config)


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="In the satellite templates file, space-to-ground XBand separation constraints must use shared constraint set 'spire_nasa_xband_coordination'",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def space_ground_xband_must_enforce_spire_nasa_xband_coordination_sat_templates(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return check_xband_shared_set(class_annos, channel_config)
