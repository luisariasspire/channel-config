from typing import Any, Dict, Optional, Union

from channel_tool.naming import class_annos_to_name
from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL,
    description="Check channel names are correct",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def check_channel_names_are_correct(
    _input: ValidationRuleInput,
    channel_id: str,
    class_annos: Dict[str, Any],
    _channel_config: Dict[str, Any],
) -> Union[str, bool]:
    expected_name = class_annos_to_name(class_annos)
    if channel_id != expected_name:
        return f"Channel name was {channel_id} but classification annotations imply {expected_name}"
    return True
