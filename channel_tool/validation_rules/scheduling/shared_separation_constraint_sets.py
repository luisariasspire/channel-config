from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Any reference to a shared constraint set must exist",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def references_to_shared_constraint_set_must_exist(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    satellite_constraints = channel_config.get("satellite_constraints", {})
    separation_constraints = satellite_constraints.get("separation", [])
    for constraint in separation_constraints:
        if constraint["type"] == "shared_constraint_set":
            constraint_name = constraint["name"]
            if constraint_name not in input.shared_constraint_sets:
                return f"References unknown shared constraint set '{constraint_name}'"
    return True


@validation_rule(
    scope=ValidationRuleScope.GENERAL,
    description="Shared separation constraint sets must not reference other sets",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def no_references_between_shared_constraint_sets(
    input: ValidationRuleInput,
) -> Union[str, bool]:
    for set_name, shared_set in input.shared_constraint_sets.items():
        for constraint in shared_set:
            if constraint["type"] == "shared_constraint_set":
                return f"Shared constraint set '{set_name}' tries to reference other shared sets, this is disallowed"
    return True
