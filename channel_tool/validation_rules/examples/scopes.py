from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="Groundstation channel example rule",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def groundstation_channel_example(
    input: ValidationRuleInput,
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    # print(f"Prototype rule gs {gs_id}, channel {channel_id}, class_annos: {class_annos}")
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="Satellite channel example rule",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_channel_example(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    # print(f"Prototype rule satellite {sat_id}, channel {channel_id}, class_annos: {class_annos}")
    return True


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Groundstation template channel example rule",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def groundstation_template_channel_example(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    # print(f"Prototype GS template channel rule, channel {channel_id}")
    return True


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="Satellite template channel example rule",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_template_channel_example(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    # print(f"Prototype satellite template channel rule, channel {channel_id}")
    return True


@validation_rule(
    scope=ValidationRuleScope.GENERAL,
    description="Example rule with general scope",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def general_example(
    input: ValidationRuleInput,
) -> Union[str, bool]:
    # print(f"Prototype general rule")
    return True
