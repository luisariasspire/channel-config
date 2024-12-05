from typing import Any, Dict, Optional

from channel_tool.validation_rules.utils import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleViolatedError,
    get_nested,
)


def is_dvbs2x(channel_config: Dict[str, Any]) -> Any:
    return (
        get_nested(
            channel_config, "classification_annotations.space_ground_sband_encoding"
        )
        == "DVBS2X"
        or get_nested(
            channel_config, "classification_annotations.space_ground_xband_encoding"
        )
        == "DVBS2X"
    )


def dvbs2x_must_have_classification_annotations(
    input: ValidationRuleInput,
) -> Optional[ValidationRuleViolatedError]:
    description = "DVBS2X encoded channels must have classification annotations"

    violation_cases = []
    for gs, gs_config in input.gs_configs.items():
        for channel, channel_config in gs_config.items():
            if "classification_annotations" not in channel_config and is_dvbs2x(
                channel_config
            ):
                violation_cases.append(f"{channel} on {gs}")

    if len(violation_cases) > 0:
        return ValidationRuleViolatedError(
            description, ValidationRuleMode.ENFORCE, violation_cases
        )
    return None


def dvbs2x_must_have_pls_value(
    input: ValidationRuleInput,
) -> Optional[ValidationRuleViolatedError]:
    description = "DVBS2X encoded channels must have pls values in their classification annotations"

    violation_cases = []
    for gs, gs_config in input.gs_configs.items():
        for channel, channel_config in gs_config.items():
            if is_dvbs2x(channel_config) and (
                not get_nested(
                    channel_config,
                    "classification_annotations.space_ground_sband_dvbs2x_pls",
                )
                and not get_nested(
                    channel_config,
                    "classification_annotations.space_ground_xband_dvbs2x_pls",
                )
            ):
                violation_cases.append(f"{channel} on {gs}")

    if len(violation_cases) > 0:
        return ValidationRuleViolatedError(
            description, ValidationRuleMode.ENFORCE, violation_cases
        )
    return None


def space_ground_sband_must_have_bandwidth(
    input: ValidationRuleInput,
) -> Optional[ValidationRuleViolatedError]:
    description = "SBAND downlink channels must have bandwidth in their classification annotations"

    violation_cases = []
    for gs, gs_config in input.gs_configs.items():
        for channel, channel_config in gs_config.items():
            if get_nested(
                channel_config, "classification_annotations.space_ground_sband"
            ) and not get_nested(
                channel_config,
                "classification_annotations.space_ground_sband_bandwidth_mhz",
            ):
                violation_cases.append(f"{channel} on {gs}")

    if len(violation_cases) > 0:
        return ValidationRuleViolatedError(
            description, ValidationRuleMode.ENFORCE, violation_cases
        )
    return None


def space_ground_xband_must_have_bandwidth(
    input: ValidationRuleInput,
) -> Optional[ValidationRuleViolatedError]:
    description = "XBAND downlink channels must have bandwidth in their classification annotations"

    violation_cases = []
    for gs, gs_config in input.gs_configs.items():
        for channel, channel_config in gs_config.items():
            if get_nested(
                channel_config, "classification_annotations.space_ground_xband"
            ) and not get_nested(
                channel_config,
                "classification_annotations.space_ground_xband_bandwidth_mhz",
            ):
                violation_cases.append(f"{channel} on {gs}")

    if len(violation_cases) > 0:
        return ValidationRuleViolatedError(
            description, ValidationRuleMode.ENFORCE, violation_cases
        )
    return None
