import os
from typing import Any, Callable, Dict, List, Optional, Set, cast

import jsonschema
from jsonschema.exceptions import best_match
from termcolor import colored

from channel_tool.asset_config import (
    infer_asset_type,
    infer_config_file,
    load_asset_config,
    locate_assets,
)
from channel_tool.typedefs import ChannelDefinition
from channel_tool.util import (
    ENVS,
    GROUND_STATION,
    GS_DIR,
    GS_TEMPLATE_FILE,
    SAT_DIR,
    SAT_TEMPLATE_FILE,
    SATELLITE,
    SCHEMA_FILE,
    SHARED_CONSTRAINT_SET,
    SHARED_SEP_CONSTRAINTS_DIR,
    load_yaml_file,
)
from channel_tool.validation_rules import (
    ValidationRule,
    ValidationRuleInput,
    ValidationRuleMode,
    ValidationRuleViolatedError,
    get_validation_rules,
)


class ValidationError(Exception):
    def __init__(
        self,
        parent: Any,
        file: Optional[str] = None,
        key: Optional[str] = None,
        count: int = 1,
    ):
        self._parent = parent
        self._file = file
        self._key = key
        self._count = count

    def __str__(self) -> str:
        return f"""Validation error: {self._parent.message}
        in {self._parent.json_path}

        (Best match of {self._count} errors found while validating {self._file}#{self._key})
        Context:
        {self._parent.context}
        """


class TemplateValidationError(Exception):
    pass


def validate_all(args: Any) -> None:
    if args.module is not None:
        rule_module_filter = lambda rule: args.module in rule.module
    else:
        rule_module_filter = lambda _: True

    if args.function is not None:
        rule_function_filter = lambda rule: args.function in rule.name
    else:
        rule_function_filter = lambda _: True

    validation_rules = get_validation_rules(rule_module_filter, rule_function_filter)

    print("Checking that satellite templates conform to the schema...")
    sat_templates: Dict[str, ChannelDefinition] = check_file_conforms_to_schema(
        SATELLITE, SAT_TEMPLATE_FILE
    )
    print(colored("PASS", "green"))

    print("Checking that ground station templates conform to the schema...")
    gs_templates: Dict[str, ChannelDefinition] = check_file_conforms_to_schema(
        GROUND_STATION, GS_TEMPLATE_FILE
    )
    print(colored("PASS", "green"))

    print(
        "Checking that satellite and ground station templates have the same set of channels"
    )
    sat_template_keys = set(sat_templates.keys())
    gs_template_keys = set(gs_templates.keys())

    for sat_key in sat_template_keys:
        if sat_key not in gs_template_keys:
            raise TemplateValidationError(
                f"{sat_key} is in {SAT_TEMPLATE_FILE} but not {GS_TEMPLATE_FILE}"
            )

    for gs_key in gs_template_keys:
        if gs_key not in sat_template_keys:
            raise TemplateValidationError(
                f"{gs_key} is in {GS_TEMPLATE_FILE} but not {SAT_TEMPLATE_FILE}"
            )
    print(colored("PASS", "green"))

    print(
        "Checking that in GS templates, classification annotations are unique to channel ID"
    )
    for channel_id_1, channel_config_1 in gs_templates.items():
        for channel_id_2, channel_config_2 in gs_templates.items():
            if (
                channel_id_1 > channel_id_2
            ):  # ensures each unordered distinct pair is considered only once.
                if (
                    channel_config_1["classification_annotations"]
                    == channel_config_2["classification_annotations"]
                ):
                    raise TemplateValidationError(
                        f"In {GS_TEMPLATE_FILE} channels {channel_id_1} and {channel_id_2} have the same classification annotations"
                    )
    print(colored("PASS", "green"))

    for env in ENVS:
        print(f"Checking {env} shared constraint sets conform to the schema ...")
        shared_constraint_sets = {}
        shared_constraint_set_dir = os.path.join(env, SHARED_SEP_CONSTRAINTS_DIR)
        if os.path.isdir(shared_constraint_set_dir):
            shared_constraint_set_files = os.listdir(shared_constraint_set_dir)
            shared_sep_constraint_names = [
                os.path.splitext(os.path.basename(p))[0]
                for p in shared_constraint_set_files
            ]
            for shared_sep_constraint_set in sorted(shared_sep_constraint_names):
                print(f"{shared_sep_constraint_set}... ", end="")
                config = check_file_conforms_to_schema(
                    SHARED_CONSTRAINT_SET,
                    os.path.join(
                        env,
                        SHARED_SEP_CONSTRAINTS_DIR,
                        shared_sep_constraint_set + ".yaml",
                    ),
                )
                shared_constraint_sets[shared_sep_constraint_set] = config
                print(colored("PASS", "green"))

        if args.assets is None:
            assets = locate_assets(env, "all")
        else:
            assets = locate_assets(env, args.assets)
        all_sats = [a for a in assets if infer_asset_type(a) == SATELLITE]
        all_stations = [a for a in assets if infer_asset_type(a) == GROUND_STATION]
        print(
            f"Starting validation for {env} config: {len(all_sats)} satellites and {len(all_stations)} groundstations"
        )
        print(f"Checking {env} satellite configs conform to the schema ...")
        all_sat_configs = {}
        for sat_id in sorted(all_sats):
            print(f"{sat_id}... ", end="")
            config = check_file_conforms_to_schema(
                SATELLITE, infer_config_file(env, sat_id)
            )
            all_sat_configs[sat_id] = config
            print(colored("PASS", "green"))

        print(f"Checking {env} groundstation configs conform to the schema ...")
        all_gs_configs = {}
        for gs_id in sorted(all_stations):
            print(f"{gs_id}... ", end="")
            config = check_file_conforms_to_schema(
                GROUND_STATION, infer_config_file(env, gs_id)
            )
            all_gs_configs[gs_id] = config
            print(colored("PASS", "green"))

        print(
            f"Checking {env} satellite configs use channel IDs from {SAT_TEMPLATE_FILE} ..."
        )
        for sat_id in sorted(all_sats):
            check_allowed_keys(
                SAT_TEMPLATE_FILE, sat_id, all_sat_configs[sat_id], sat_template_keys
            )
        print(colored("PASS", "green"))

        print(
            f"Checking {env} groundstation configs use channel IDs from {GS_TEMPLATE_FILE} ..."
        )
        for gs_id in sorted(all_stations):
            check_allowed_keys(
                GS_TEMPLATE_FILE, gs_id, all_gs_configs[gs_id], gs_template_keys
            )
        print(colored("PASS", "green"))

        print(f"Running validation rules on {env} config ...")
        validation_rule_input = ValidationRuleInput(
            SAT_TEMPLATE_FILE,
            sat_templates,
            all_sat_configs,
            GS_TEMPLATE_FILE,
            gs_templates,
            all_gs_configs,
            shared_constraint_sets,
        )
        run_validation_rules(validation_rules, validation_rule_input)
        print(f"Validation complete for {env}")


def check_allowed_keys(
    template_file: str, asset: str, config: ChannelDefinition, allowed_keys: Set[str]
) -> None:
    for key in config:
        if key not in allowed_keys:
            raise TemplateValidationError(
                f"Channel ID {key} in {asset} is absent from {template_file}"
            )


def check_file_conforms_to_schema(asset_type: str, cf: str) -> Any:
    config = load_yaml_file(cf)

    if asset_type == GROUND_STATION or asset_type == SATELLITE:
        for key in config:
            c = config[key]
            check_element_conforms_to_schema(asset_type, c, file=cf, key=key)
    elif asset_type == SHARED_CONSTRAINT_SET:
        check_element_conforms_to_schema(asset_type, config, file=cf, key=None)
    else:
        raise Exception(f"Unknown asset type {asset_type}")
    return config


def check_element_conforms_to_schema(
    asset_type: str, config: Any, file: str, key: Optional[str]
) -> None:
    schema = load_schema(asset_type)
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(config))  # type: ignore
    if errs:
        raise ValidationError(best_match(errs), file=file, key=key, count=len(errs))


def run_validation_rule(
    rule: ValidationRule,
    input: ValidationRuleInput,
) -> Optional[ValidationRuleViolatedError]:
    print(f"    Rule {rule.name} ... ", end="")
    result = rule.function(input)
    if not result:
        print(colored("PASS", "green"))
    else:
        print(colored("FAIL", "red"))
    return result


def run_validation_rules(
    validation_rules: Dict[str, List[ValidationRule]],
    validation_rule_input: ValidationRuleInput,
) -> None:
    results = {}

    for module, module_rules in validation_rules.items():
        print(f"  Module {module}")
        for rule in module_rules:
            results[f"{rule.module}.{rule.name}"] = (
                rule,
                run_validation_rule(rule, validation_rule_input),
            )

    fail_results = {
        rulestring: (result[0], cast(ValidationRuleViolatedError, result[1]))
        for rulestring, result in results.items()
        if result[1] is not None
    }

    complain_fail_results = {
        rulestring: result
        for rulestring, result in fail_results.items()
        if result[1].mode == ValidationRuleMode.COMPLAIN
    }

    for rulestring, result in complain_fail_results.items():
        print(
            "{0}: Rule {1} failed:\n\tMode: {2}\n\tModule: {3}\n\tDescription: {4}\n\tViolation cases: \n\t - {5}".format(
                colored("WARN", "yellow"),
                result[0].name,
                result[1].mode,
                result[0].module,
                result[1].description,
                "\n\t - ".join(result[1].violation_cases),
            ),
        )

    enforce_fail_results = {
        rulestring: result
        for rulestring, result in fail_results.items()
        if result[1].mode == ValidationRuleMode.ENFORCE
    }

    for rulestring, result in enforce_fail_results.items():
        print(
            "{0}: {1} failed:\n\tMode: {2}\n\tModule: {3}\n\tDescription: {4}\n\tViolation cases: \n\t - {5}".format(
                colored("ERROR", "red"),
                result[0].name,
                result[1].mode,
                result[0].module,
                result[1].description,
                "\n\t - ".join(result[1].violation_cases),
            ),
        )

    if len(enforce_fail_results) > 0:
        raise ValidationError(Exception("One or more enforced validation rules failed"))


# Memoize the JSON Schema definitions.
loaded_gs_schema = None
loaded_sat_schema = None
loaded_shared_constraint_set_schema = None


def load_schema(asset_type: str) -> Any:
    if asset_type == GROUND_STATION:
        return load_gs_schema()
    elif asset_type == SATELLITE:
        return load_sat_schema()
    elif asset_type == SHARED_CONSTRAINT_SET:
        return load_shared_constraint_set_schema()
    else:
        raise Exception(f"Unknown asset type {asset_type}")


def load_shared_constraint_set_schema() -> Any:
    global loaded_shared_constraint_set_schema
    if not loaded_shared_constraint_set_schema:
        loaded_shared_constraint_set_schema = load_yaml_file(SCHEMA_FILE)[
            "shared_separation_constraint_sets_schema"
        ]
    return loaded_shared_constraint_set_schema


def load_gs_schema() -> Any:
    global loaded_gs_schema
    if not loaded_gs_schema:
        loaded_gs_schema = load_yaml_file(SCHEMA_FILE)["gs_schema"]
    return loaded_gs_schema


def load_sat_schema() -> Any:
    global loaded_sat_schema
    if not loaded_sat_schema:
        loaded_sat_schema = load_yaml_file(SCHEMA_FILE)["sat_schema"]
    return loaded_sat_schema
