import importlib
import inspect
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from channel_tool.typedefs import ChannelDefinition


class ValidationRuleInput:
    def __init__(
        self,
        sat_templates_file: str,
        sat_templates: Dict[str, ChannelDefinition],
        sat_configs: Dict[str, Dict[str, Optional[ChannelDefinition]]],
        gs_templates_file: str,
        gs_templates: Dict[str, ChannelDefinition],
        gs_configs: Dict[str, Dict[str, Optional[ChannelDefinition]]],
        shared_constraint_sets: Dict[str, Any],
    ):
        self.sat_templates_file = sat_templates_file
        self.sat_templates = sat_templates
        self.sat_configs = sat_configs
        self.gs_templates_file = gs_templates_file
        self.gs_templates = gs_templates
        self.gs_configs = gs_configs
        self.shared_constraint_sets = shared_constraint_sets


class ValidationRuleMode(Enum):
    ENFORCE = 1
    COMPLAIN = 2


class ValidationRuleScope(Enum):
    GROUNDSTATION_TEMPLATE_CHANNEL = 1
    SATELLITE_TEMPLATE_CHANNEL = 2
    GROUNDSTATION_CHANNEL = 3
    SATELLITE_CHANNEL = 4
    GENERAL = 5


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


validation_rules: Dict[str, List[ValidationRule]] = {}


def validation_rule(
    scope: ValidationRuleScope, description: str, mode: ValidationRuleMode
) -> Callable[
    [Any], Callable[[ValidationRuleInput], Optional[ValidationRuleViolatedError]]
]:
    def decorator(
        func: Any,
    ) -> Callable[[ValidationRuleInput], Optional[ValidationRuleViolatedError]]:
        def wrapper(
            input: ValidationRuleInput,
        ) -> Optional[ValidationRuleViolatedError]:
            violation_cases: List[str] = []
            match scope:
                case ValidationRuleScope.GROUNDSTATION_TEMPLATE_CHANNEL:
                    for channel_id, channel_config in input.gs_templates.items():
                        interpret_rule_result(
                            violation_cases,
                            func(input, channel_id, channel_config),
                            f"{channel_id} in {input.sat_templates_file}",
                        )
                case ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL:
                    for channel_id, channel_config in input.sat_templates.items():
                        class_annos = input.gs_templates[channel_id][
                            "classification_annotations"
                        ]
                        interpret_rule_result(
                            violation_cases,
                            func(input, channel_id, class_annos, channel_config),
                            f"{channel_id} in {input.sat_templates_file}",
                        )
                case ValidationRuleScope.GROUNDSTATION_CHANNEL:
                    for gs_id, gs_config in input.gs_configs.items():
                        for channel_id, channel_config in gs_config.items():
                            class_annos = input.gs_templates[channel_id][
                                "classification_annotations"
                            ]
                            interpret_rule_result(
                                violation_cases,
                                func(
                                    input,
                                    gs_id,
                                    channel_id,
                                    class_annos,
                                    channel_config,
                                ),
                                f"{channel_id} on {gs_id}",
                            )
                case ValidationRuleScope.SATELLITE_CHANNEL:
                    for sat_id, sat_config in input.sat_configs.items():
                        for channel_id, channel_config in sat_config.items():
                            class_annos = input.gs_templates[channel_id][
                                "classification_annotations"
                            ]
                            interpret_rule_result(
                                violation_cases,
                                func(
                                    input,
                                    sat_id,
                                    channel_id,
                                    class_annos,
                                    channel_config,
                                ),
                                f"{channel_id} on {sat_id}",
                            )
                case ValidationRuleScope.GENERAL:
                    interpret_rule_result(
                        violation_cases, func(input), "General rule failure"
                    )
                case _:
                    raise Exception(f"Unknown validation rule scope {scope}")

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


def interpret_rule_result(
    violation_cases: List[str], rule_result: Union[str, bool], prefix: str
) -> None:
    if rule_result == True:
        return
    case_text = prefix
    if isinstance(rule_result, str):
        case_text = f"{case_text}: {rule_result}"
    violation_cases.append(case_text)


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
