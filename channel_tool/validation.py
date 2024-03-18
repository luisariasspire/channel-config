import os
from typing import Any, Callable, Dict, Optional, Set

import jsonschema
from jsonschema.exceptions import best_match
from termcolor import colored

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
    load_yaml_file,
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


def validate_all() -> None:
    print(f"Validating satellite templates...")
    validate_file(SATELLITE, SAT_TEMPLATE_FILE)
    print(colored("PASS", "green"))

    print(f"Validating ground station templates...")
    validate_file(GROUND_STATION, GS_TEMPLATE_FILE)
    print(colored("PASS", "green"))

    print(
        f"Validating satellite and ground station templates have the same set of channels"
    )
    sat_templates: Dict[str, ChannelDefinition] = load_yaml_file(SAT_TEMPLATE_FILE)
    gs_templates: Dict[str, ChannelDefinition] = load_yaml_file(GS_TEMPLATE_FILE)

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
        f"Validating channels in satellite and ground station templates have legal and enabled set to false"
    )
    for templates, template_file in [
        (sat_templates, SAT_TEMPLATE_FILE),
        (gs_templates, GS_TEMPLATE_FILE),
    ]:
        for key, config in templates.items():
            for field in ["legal", "enabled"]:
                if config[field] != False:
                    raise TemplateValidationError(
                        f"Channel {key} in {template_file} should have {field} set to false"
                    )
    print(colored("PASS", "green"))

    for env in ENVS:
        print(f"Validating {env} satellites...")
        sat_dir = os.path.join(env, SAT_DIR)
        all_sats = os.listdir(sat_dir)
        for sf in sorted(all_sats):
            print(f"{sf}... ", end="")
            validate_file(SATELLITE, os.path.join(sat_dir, sf), sat_template_keys)
            print(colored("PASS", "green"))

        print(f"Validating {env} ground stations...")
        gs_dir = os.path.join(env, GS_DIR)
        all_stations = os.listdir(gs_dir)
        for gsf in sorted(all_stations):
            print(f"{gsf}... ", end="")
            validate_file(GROUND_STATION, os.path.join(gs_dir, gsf), gs_template_keys)
    print("All passed!")


def validate_file(
    asset_type: str, cf: str, allowed_keys: Optional[Set[str]] = None
) -> None:
    config = load_yaml_file(cf)
    for key in config:
        c = config[key]
        validate_one(asset_type, c, file=cf, key=key)
        if allowed_keys and key not in allowed_keys:
            raise TemplateValidationError(
                f"Channel ID {key} in {cf} is absent from {asset_type} template_file"
            )


def validate_one(
    asset_type: str, config: ChannelDefinition, file: str, key: str
) -> None:
    schema = load_schema(asset_type)
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(config))  # type: ignore
    if errs:
        raise ValidationError(best_match(errs), file=file, key=key, count=len(errs))


# Memoize the JSON Schema definitions.
loaded_gs_schema = None
loaded_sat_schema = None


def load_schema(asset_type: str) -> Any:
    if asset_type == GROUND_STATION:
        return load_gs_schema()
    elif asset_type == SATELLITE:
        return load_sat_schema()
    else:
        raise Exception(f"Unknown asset type {asset_type}")


def load_gs_schema() -> Any:
    global loaded_gs_schema
    if not loaded_gs_schema:
        # File has "gs_schema", "sat_schema" and "definitions" as top-level fields.
        loaded_gs_schema = load_yaml_file(SCHEMA_FILE)["gs_schema"]
    return loaded_gs_schema


def load_sat_schema() -> Any:
    global loaded_sat_schema
    if not loaded_sat_schema:
        # File has "gs_schema", "sat_schema" and "definitions" as top-level fields.
        loaded_sat_schema = load_yaml_file(SCHEMA_FILE)["sat_schema"]
    return loaded_sat_schema
