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
        self.channel_id_to_class_annos = {}

        for channel_id, channel_config in gs_templates.items():
            self.channel_id_to_class_annos[channel_id] = channel_config[
                "classification_annotations"
            ]


class ValidationRuleMode(Enum):
    ENFORCE = 1
    COMPLAIN = 2


class ValidationRuleScope(Enum):
    # rule is run once for each channel in gs_templates.yaml
    GROUNDSTATION_TEMPLATE_CHANNEL = 1
    # rule is run once for each channel in sat_templates.yaml
    SATELLITE_TEMPLATE_CHANNEL = 2
    # rule is run once for each channel in each groundstation yaml file
    GROUNDSTATION_CHANNEL = 3
    # rule is run once for each channel in each satellite yaml file
    SATELLITE_CHANNEL = 4
    # rule is run once for each groundstation yaml file, and gets passed all its channels
    GROUNDSTATION = 5
    # rule is run once for each satellite yaml file, and gets passed all its channels
    SATELLITE = 6
    # rule is run once, and can access all aspects of channel config
    GENERAL = 7


class ValidationRuleEnv(str, Enum):
    PRODUCTION_ONLY = "production"
    STAGING_ONLY = "staging"


class ValidationRuleViolatedError:
    def __init__(
        self,
        description: str,
        mode: ValidationRuleMode,
        scope: ValidationRuleScope,
        violation_cases: List[str],
    ):
        self.description = description
        self.mode = mode
        self.scope = scope
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
    scope: ValidationRuleScope,
    description: str,
    mode: ValidationRuleMode,
    env: Optional[ValidationRuleEnv] = None,
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
                        class_annos = input.channel_id_to_class_annos[channel_id]
                        interpret_rule_result(
                            violation_cases,
                            func(input, channel_id, class_annos, channel_config),
                            f"{channel_id} in {input.gs_templates_file}",
                        )
                case ValidationRuleScope.SATELLITE_TEMPLATE_CHANNEL:
                    for channel_id, channel_config in input.sat_templates.items():
                        class_annos = input.channel_id_to_class_annos[channel_id]
                        interpret_rule_result(
                            violation_cases,
                            func(input, channel_id, class_annos, channel_config),
                            f"{channel_id} in {input.sat_templates_file}",
                        )
                case ValidationRuleScope.GROUNDSTATION_CHANNEL:
                    for gs_id, gs_config in input.gs_configs.items():
                        for channel_id, channel_config in gs_config.items():
                            class_annos = input.channel_id_to_class_annos[channel_id]
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
                            class_annos = input.channel_id_to_class_annos[channel_id]
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
                case ValidationRuleScope.SATELLITE:
                    for sat_id, sat_configs in input.sat_configs.items():
                        interpret_rule_result(
                            violation_cases,
                            func(
                                input,
                                sat_id,
                                sat_configs,
                                input.channel_id_to_class_annos,
                            ),
                            f"{sat_id}",
                        )
                case ValidationRuleScope.GROUNDSTATION:
                    for gs_id, gs_configs in input.gs_configs.items():
                        interpret_rule_result(
                            violation_cases,
                            func(
                                input,
                                gs_id,
                                gs_configs,
                                input.channel_id_to_class_annos,
                            ),
                            f"{gs_id}",
                        )
                case ValidationRuleScope.GENERAL:
                    interpret_rule_result(
                        violation_cases, func(input), "General rule failure"
                    )

                case _:
                    raise Exception(f"Unknown validation rule scope {scope}")

            if len(violation_cases) > 0:
                return ValidationRuleViolatedError(
                    description, mode, scope, violation_cases
                )
            return None

        setattr(wrapper, "_arg_rule_env", env)
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
    matching_rules = {}
    for path in Path("channel_tool/validation_rules").rglob("*.py"):
        dir = path.parent.__str__().replace("/", ".")
        package = importlib.import_module(f"{dir}.{path.stem}")
    for module_name, module_rules in validation_rules.items():
        module_matching_rules = [
            rule
            for rule in module_rules
            if rule_module_filter(rule) and rule_function_filter(rule)
        ]
        if len(module_matching_rules) > 0:
            print(f"Found {len(module_matching_rules)} rules in module {module_name}:")
            for rule in module_matching_rules:
                print(f"  - {rule.name}")
            matching_rules[module_name] = module_matching_rules
    return matching_rules


def filter_validation_rules_by_env(
    validation_rules: Dict[str, List[ValidationRule]], target_environment: str
) -> Dict[str, List[ValidationRule]]:
    """
    Filter validation rules based on target environment.

    Validation rules can specify an optional environment argument. If this is specified, it means run
    the rule only in that environment. If the environment is not specified, this is treated as a wildcard.
    """
    env_validation_rules = {}
    for module_name, module_rules in validation_rules.items():
        module_env_rules = []
        for rule in module_rules:
            rule_env = getattr(
                rule.function,
                "_arg_rule_env",
            )
            if not rule_env:
                module_env_rules.append(rule)
            elif rule_env.value == target_environment:
                module_env_rules.append(rule)
            else:
                print(
                    f"Filtering out {rule.name} for validation in {target_environment} environment."
                )
                continue
        if module_env_rules:
            env_validation_rules[module_name] = module_env_rules
    return env_validation_rules
