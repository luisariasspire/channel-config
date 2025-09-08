"""
Rules to validate channel configs applicable to specifc ground station providers
"""

from typing import Any, Dict, TypedDict, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    validation_rule,
)


class ConstraintSchema(TypedDict):
    required: list[str]
    forbidden: list[str]


Provider = str
Errors = list[str]

SAT_CONSTRAINT_SCHEMA: dict[Provider, ConstraintSchema] = {
    "SPIRE": {
        "required": [],
        "forbidden": ["budget_name", "fixed_contact_duration"],
    },
    "KSAT": {
        "required": ["budget_name", "fixed_contact_duration"],
        "forbidden": [],
    },
}

GS_CONSTRAINT_SCHEMA: dict[Provider, ConstraintSchema] = {
    "SPIRE": {
        "required": [],
        "forbidden": ["dollar_cost"],
    },
    "KSAT": {
        "required": ["dollar_cost"],
        "forbidden": [],
    },
}


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Validate ground station provider specific satellite constraints",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def validate_sat_constraints_for_gs_provider(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    try:
        provider: Provider = class_annos["provider"]
    except KeyError:
        return "No provider specified in class annotations"

    try:
        schema = SAT_CONSTRAINT_SCHEMA[provider]
    except KeyError:
        # No constraint schema for provider, assume validation not required.
        return True

    errors: Errors = _check_constraints(
        constraints=channel_config.get("satellite_constraints", {}), schema=schema
    )

    if errors:
        return f"For provider '{provider}' the following validation errors are detected: {errors}"
    else:
        return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Validate ground station provider specific ground station constraints",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def validate_gs_constraints_for_gs_provider(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    try:
        provider: Provider = class_annos["provider"]
    except KeyError:
        return "No provider specified in class annotations"

    try:
        schema = GS_CONSTRAINT_SCHEMA[provider]
    except KeyError:
        # No constraint schema for provider, assume validation not required.
        return True

    errors: Errors = _check_constraints(
        constraints=channel_config.get("ground_station_constraints", {}), schema=schema
    )

    if errors:
        return f"For provider '{provider}' the following validation errors are detected: {errors}"
    else:
        return True


def _check_constraints(constraints: dict[str, Any], schema: ConstraintSchema) -> Errors:
    """
    Check channel config constraints against provided schema and return errors (list[str]).

    If empty list returned, validation has passed.
    """
    errors: Errors = []
    errors += [
        f"Missing field '{missing_field}' in constraints"
        for missing_field in set(schema.get("required", [])) - set(constraints.keys())
    ]
    errors += [
        f"Forbidden field '{forbidden_field}' in constraints"
        for forbidden_field in set(schema.get("forbidden", []))
        & set(constraints.keys())
    ]

    return errors
