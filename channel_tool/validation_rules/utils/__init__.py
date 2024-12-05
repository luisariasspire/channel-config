from enum import Enum
from typing import Any, Dict, List, Optional

from channel_tool.typedefs import ChannelDefinition


class ValidationRuleInput:
    def __init__(
        self,
        sat_configs: Dict[str, Dict[str, Optional[ChannelDefinition]]],
        gs_configs: Dict[str, Dict[str, Optional[ChannelDefinition]]],
    ):
        self.sat_configs = sat_configs
        self.gs_configs = gs_configs


class ValidationRuleMode(Enum):
    ENFORCE = 1
    COMPLAIN = 2


class ValidationRuleViolatedError:
    def __init__(
        self, description: str, mode: ValidationRuleMode, violation_cases: List[str]
    ):
        self.description = description
        self.mode = mode
        self.violation_cases = violation_cases


def get_nested(d: Dict[str, Any], keys: str) -> Optional[Any]:
    keys_list = keys.split(".")

    key = keys_list.pop(0)

    if key not in d:
        return None

    if not keys_list:
        return d[key]

    remaining_keys = ".".join(keys_list)

    return get_nested(d[key], remaining_keys)
