from typing import Any, Dict, Optional

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)

"""
    Rule to check that GS config classification annotations match those in GS templates
"""


@validation_rule(
    scope=ValidationRuleScope.GROUNDSTATION_CHANNEL,
    description="GS config classification annotation must match those in GS template",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def gs_class_annos_must_match_template(
    gs_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> bool:
    if class_annos != channel_config["classification_annotations"]:
        return False
    return True
