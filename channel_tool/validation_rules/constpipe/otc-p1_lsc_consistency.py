import json
from typing import Any, Dict, Optional, Union

from channel_tool.validation_rules import (
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleScope,
    ValidationRuleViolatedError,
    validation_rule,
)

OTC_P1_FMS = ["FM211", "FM212", "FM213", "FM214", "FM215", "FM216", "FM217", "FM218"]
OTC_P1_EXPECTED_LSC = [
    dict(topics=["otc_prio_0"], offset=0),
    dict(topics=["*"], offset=30),
    dict(topics=["otc_prio_0"], offset=60),
    dict(topics=["*"], offset=90),
]


@validation_rule(
    scope=ValidationRuleScope.SATELLITE_CHANNEL,
    description="OCT-P1 TXO channels have dedicated time for Oort topic otc_prio_0",
    mode=ValidationRuleMode.ENFORCE,
)  # type: ignore
def satellite_channel_otc_p1_has_lsc(
    input: ValidationRuleInput,
    sat_id: str,
    channel_id: str,
    class_annos: Dict[str, Any],
    channel_config: Dict[str, Any],
) -> Union[str, bool]:
    if not sat_id in OTC_P1_FMS:
        return True
    if not class_annos["directionality"] == "TXO":
        return True
    # Right FM & right channel - time to validate:
    # window_parameters must exist
    if "window_parameters" not in channel_config:
        return "Element missing: window_parameters"
    window_parameters = channel_config["window_parameters"]

    # link_state_cues must exist
    if "link_state_cues" not in window_parameters:
        return "Element missing: link_state_cues"
    link_state_cues = window_parameters["link_state_cues"]

    # link_state_cues must be identical
    if OTC_P1_EXPECTED_LSC == link_state_cues:
        return True

    return (
        f"Expected: window_parameters.link_state_cues="
        + f" {json.dumps(OTC_P1_EXPECTED_LSC)}, Actual: {json.dumps(link_state_cues)}"
    )
