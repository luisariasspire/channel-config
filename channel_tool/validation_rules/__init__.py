import importlib
import inspect
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


class ValidationRule:
    def __init__(
        self,
        module: str,
        name: str,
        function: Callable[
            [ValidationRuleInput], Optional[ValidationRuleViolatedError]
        ],
    ):
        self.module = module
        self.name = name
        self.function = function


def get_nested(d: Dict[str, Any], keys_list: List[str]) -> Optional[Any]:
    key = keys_list.pop(0)

    if key not in d:
        return None

    if not keys_list:
        return d[key]

    return get_nested(d[key], keys_list)


def class_anno(channel_config: Dict[str, Any], key: str) -> Any:
    return get_nested(channel_config, ["classification_annotations", key])


validation_rules: Dict[str, List[ValidationRule]] = {}


def validation_rule(
    scope: str, description: str, mode: ValidationRuleMode
) -> Callable[
    [Any], Callable[[ValidationRuleInput], Optional[ValidationRuleViolatedError]]
]:
    def decorator(
        func: Any,
    ) -> Callable[[ValidationRuleInput], Optional[ValidationRuleViolatedError]]:
        def wrapper(
            input: ValidationRuleInput,
        ) -> Optional[ValidationRuleViolatedError]:
            violation_cases = []
            if scope == "groundstation_channel":
                for gs_id, gs_config in input.gs_configs.items():
                    for channel_id, channel_config in gs_config.items():
                        if not func(gs_id, channel_id, channel_config):
                            violation_cases.append(f"{channel_id} on {gs_id}")
            if len(violation_cases) > 0:
                return ValidationRuleViolatedError(description, mode, violation_cases)
            return None

        module_name = func.__module__.replace("channel_tool.validation_rules.", "")
        module_rules = validation_rules.get(module_name, [])
        if not module_rules:
            validation_rules[module_name] = module_rules
        module_rules.append(
            ValidationRule(module=module_name, name=func.__name__, function=wrapper)
        )
        return wrapper

    return decorator


def get_validation_rules(
    rule_module_filter: Callable[[Any], bool],
    rule_function_filter: Callable[[Any], bool],
) -> Dict[str, List[ValidationRule]]:
    print(f"Importing validation rules")
    for path in Path("channel_tool/validation_rules").rglob("*.py"):
        dir = path.parent.__str__().replace("/", ".")
        package = importlib.import_module(f"{dir}.{path.stem}")
    for module_name, module_rules in validation_rules.items():
        print(f"Found {len(module_rules)} rules in module {module_name}:")
        for rule in module_rules:
            print(f"  - {rule.name}")
    return validation_rules
