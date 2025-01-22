from typing import Any, Dict, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    validation_rule,
)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Groundstation template channels must have 'enabled' flag set to false",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_template_channels_must_have_enabled_false(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return not channel_config["enabled"]


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Groundstation template channels must have 'legal' flag set to false",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_template_channels_must_have_legal_false(
    input: ValidationRuleInput,
    channel_id: str,
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return not channel_config["legal"]


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="Satellite template channels must have 'enabled' flag set to false",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def sat_template_channels_must_have_enabled_false(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return not channel_config["enabled"]


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL,
    description="Satellite template channels must have 'legal' flag set to false",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def sat_template_channels_must_have_legal_false(
    input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    return not channel_config["legal"]
